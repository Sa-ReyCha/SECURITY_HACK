"""
generate_synthetic_data.py
--------------------------
Generates a SINGLE unified CSV (output/logs.csv) combining system logs and
LLM logs in one wide table.

Columns that do not apply to a given log type are left empty (null), so the
dataset has realistic null patterns depending on sap_function_log_type:

  System log types  → INFO | WARNING | ERROR | DEBUG | AUDIT | PERF
    • LLM-specific cols  (llm_model_id … llm_stream)  → null
    • sap_llm_response_size / sap_llm_response_time    → null

  LLM log types     → LLM_REQUEST | LLM_ERROR | LLM_TIMEOUT
    • All LLM cols fully populated
    • service_id / http_status_code / client_ip        → null
    • sap_llm_response_size / sap_llm_response_time    → populated

All reference data is loaded from reference_data/*.json
"""

import csv
import hashlib
import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION  ─ all tunable parameters in one place
# ══════════════════════════════════════════════════════════════════════════════

# ── general ───────────────────────────────────────────────────────────────────
SEED       = 42
N_ROWS     = 1_220_600          # total rows in the output CSV
PCT_SYSTEM = 0.60           # fraction that are System logs (rest are LLM)
START_DATE = datetime(2026, 3,  23,  0,  0,  0, tzinfo=timezone.utc)  # (year, month, day, hour, minute, second)
END_DATE   = datetime(2026, 3, 28, 0, 0, 0, tzinfo=timezone.utc)  
                # (year, month, day, hour, minute, second)
# Resolve paths relative to this script's location so it can be run from any directory
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output")
REF_DIR    = os.path.join(_SCRIPT_DIR, "reference_data")

# ── system log-type weights ───────────────────────────────────────────────────
# Edit the numbers below to change how often each System log type appears.
# Weights are relative (do not need to sum to 100).
# Types and labels must stay in sync with reference_data/sap_log_types.json.
SYS_LOG_TYPE_WEIGHTS = {
    "INFO":     40,
    "WARNING":  20,
    "ERROR":    15,
    "DEBUG":    10,
    "AUDIT":    10,
    "PERF":      5,
    "SECURITY":  8,
}

# ── LLM log-type weights ──────────────────────────────────────────────────────
# Weights for LLM_REQUEST / LLM_ERROR / LLM_TIMEOUT (relative).
LLM_LOG_TYPE_WEIGHTS = {
    "LLM_REQUEST": 70,
    "LLM_ERROR":   20,
    "LLM_TIMEOUT": 10,
}

# ── LLM finish-reason weights (for successful LLM_REQUEST rows) ───────────────
LLM_FINISH_REASON_WEIGHTS = {
    "stop":           70,
    "length":         25,
    "content_filter":  5,
}

# ── HTTP status-code weights per System log type ──────────────────────────────
HTTP_STATUS_WEIGHTS = {
    "ERROR":   {"codes": [500, 502, 503, 504, 400, 401, 403, 404],
                "weights": [30,  10,  10,   5,  20,  10,  10,   5]},
    "WARNING": {"codes": [200, 206, 429, 408, 400],
                "weights": [40,  10,  20,  20,  10]},
    "DEFAULT": {"codes": [200, 201, 204, 301, 302],
                "weights": [70,  10,  10,   5,   5]},
}

# ── client IP pool ────────────────────────────────────────────────────────────
# A fixed pool of client IPs is generated at startup so IPs repeat realistically.
# Adjust the counts to control variety.
N_REGULAR_CLIENT_IPS   = 80   # normal clients (high repeat frequency)
N_INTERNAL_CLIENT_IPS  = 20   # internal/service IPs (192.168.x.x)
N_SUSPICIOUS_CLIENT_IPS = 5   # IPs that appear more in SECURITY rows

# ── LLM numeric ranges ────────────────────────────────────────────────────────
LLM_PROMPT_TOKENS_RANGE      = (50,  2_000)   # (min, max) tokens in the prompt
LLM_COMPLETION_TOKENS_RANGE  = (30,  1_500)   # tokens in the completion
LLM_RESPONSE_TIME_RANGE_MS   = (200, 15_000)  # latency for successful requests
LLM_ERROR_RESPONSE_TIME_MS   = (200,  3_000)  # latency for LLM_ERROR rows
LLM_TIMEOUT_RESPONSE_TIME_MS = (28_000, 35_000)  # latency for LLM_TIMEOUT rows
LLM_RESPONSE_SIZE_RANGE      = (256, 32_768)  # bytes
LLM_TEMPERATURE_RANGE        = (0.0,    1.5)
LLM_TOP_P_RANGE              = (0.5,    1.0)

# ── vendor / error pools and LLM error messages are loaded from reference_data ─
# Edit the following JSON files to add/remove entries (no script changes needed):
#   reference_data/sap_vendors.json
#   reference_data/sap_errors.json
#   reference_data/llm_error_messages.json

# ══════════════════════════════════════════════════════════════════════════════

random.seed(SEED)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── load reference data ───────────────────────────────────────────────────────
def _load(filename):
    with open(os.path.join(REF_DIR, filename), encoding="utf-8") as f:
        return json.load(f)

regions       = _load("regions.json")
environments  = _load("environments.json")
applications  = _load("sap_applications.json")
source_types  = _load("sap_source_types.json")
log_types_ref = _load("sap_log_types.json")
llm_models    = _load("llm_models.json")
services      = _load("services.json")
http_methods  = _load("http_methods.json")
content_types = _load("content_types.json")
llm_prompts       = _load("llm_prompts.json")
sys_messages      = _load("sys_messages.json")
SAP_VENDORS       = _load("sap_vendors.json")
SAP_ERRORS        = _load("sap_errors.json")
LLM_ERROR_MESSAGES = _load("llm_error_messages.json")

# ── unified CSV column order ───────────────────────────────────────────────────
COLUMNS = [
    # ── elastic / pipeline metadata ──────────────────────────────────────────
    "_id",
    "_ignored",
    "_index",
    "_score",
    # ── event core ───────────────────────────────────────────────────────────
    "@timestamp",
    "@version",
    "event_code_version",
    "event_hash",
    "@event_time_requested",
    # ── HTTP headers ─────────────────────────────────────────────────────────
    "headers_content_type",
    "headers_http_host",
    "headers_http_request_method",
    "heathers_request_path",          # note: typo preserved from original schema
    # ── SAP / function fields (always present) ───────────────────────────────
    "sap_function_application",
    "sap_source_type",
    "sap_function_log_type",
    "sap_function_message",
    "sap_app_env",
    # ── LLM response metrics (present for LLM log types; null for system) ────
    "sap_llm_response_size",
    "sap_llm_response_time",
    # ── region enrichment ────────────────────────────────────────────────────
    "region_id",
    "region_name",
    "region_code",
    "macro_region",
    # ── system-log–only columns (null for LLM log types) ─────────────────────
    "service_id",
    "http_status_code",
    "client_ip",
    # ── LLM-log–only columns (null for system log types) ─────────────────────
    "llm_model_id",
    "llm_provider",
    "llm_prompt_id",
    "llm_prompt_category",
    "llm_prompt",
    "llm_prompt_tokens",
    "llm_completion_tokens",
    "llm_total_tokens",
    "llm_response_time_ms",
    "llm_response_size_bytes",
    "llm_status",
    "llm_error_message",
    "llm_cost_usd",
    "llm_temperature",
    "llm_top_p",
    "llm_stream",
    "llm_finish_reason",
]

# ── helpers ────────────────────────────────────────────────────────────────────
def rand_ts(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))

def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

# ── build client IP pool once at module level ─────────────────────────────────
def _build_ip_pool() -> tuple[list[str], list[str]]:
    regular = [
        ".".join(str(random.randint(1, 254)) for _ in range(4))
        for _ in range(N_REGULAR_CLIENT_IPS)
    ]
    internal = [
        f"192.168.{random.randint(0,9)}.{random.randint(1,254)}"
        for _ in range(N_INTERNAL_CLIENT_IPS)
    ]
    suspicious = [
        ".".join(str(random.randint(1, 254)) for _ in range(4))
        for _ in range(N_SUSPICIOUS_CLIENT_IPS)
    ]
    return regular + internal, suspicious

_REGULAR_IPS, _SUSPICIOUS_IPS = _build_ip_pool()
_ALL_IPS = _REGULAR_IPS + _SUSPICIOUS_IPS

def rand_ip(log_type: str = "") -> str:
    """Return a client IP.  SECURITY rows are 4× more likely to get a suspicious IP."""
    if log_type == "SECURITY" and random.random() < 0.40:
        return random.choice(_SUSPICIOUS_IPS)
    # slight bias: internal IPs are less frequent
    return random.choice(_ALL_IPS)

def rand_path(app_id: str, source_type: str) -> str:
    templates = [
        f"/api/v1/{app_id}/execute",
        f"/api/v2/{app_id}/query",
        f"/sap/opu/odata/{app_id}/EntitySet",
        f"/sap/bc/rest/{source_type.lower()}/invoke",
        f"/api/{app_id}/status",
        f"/api/v1/{app_id}/batch",
        f"/btp/event/{app_id}/publish",
    ]
    return random.choice(templates)

def weighted_log_type() -> str:
    """Pick a system log type using SYS_LOG_TYPE_WEIGHTS."""
    types   = list(SYS_LOG_TYPE_WEIGHTS.keys())
    weights = list(SYS_LOG_TYPE_WEIGHTS.values())
    return random.choices(types, weights=weights, k=1)[0]

def sys_message(log_type: str, app_id: str, source_type: str) -> str:
    """Pick a random message template for the given log type and resolve variables."""
    templates = sys_messages.get(log_type, ["{app} log event."])
    template  = random.choice(templates)
    return template.format(
        app=app_id,
        source=source_type,
        tps=random.randint(50, 2000),
        latency=random.randint(100, 3000),
        cpu=random.randint(10, 95),
        gc=random.randint(5, 500),
        pool=random.randint(50, 99),
        heap=random.randint(128, 4096),
        deg=random.randint(5, 40),
        iowait=random.randint(1, 200),
        qdepth=random.randint(0, 500),
    )

def rand_prompt(region_name: str, app_id: str) -> tuple[str, str, str]:
    """Returns (prompt_id, prompt_category, prompt_text)."""
    entry = random.choice(llm_prompts)
    text  = entry["template"].format(
        region=region_name,
        vendor=random.choice(SAP_VENDORS),
        q=random.randint(1, 4),
        error=random.choice(SAP_ERRORS),
        app=app_id,
    )
    return entry["id"], entry["category"], text

def http_status_for_log_type(log_type: str) -> int:
    cfg = HTTP_STATUS_WEIGHTS.get(log_type, HTTP_STATUS_WEIGHTS["DEFAULT"])
    return random.choices(cfg["codes"], weights=cfg["weights"])[0]

# ── empty row template ─────────────────────────────────────────────────────────
def empty_row() -> dict:
    return {col: "" for col in COLUMNS}

# ══════════════════════════════════════════════════════════════════════════════
# Row generators
# ══════════════════════════════════════════════════════════════════════════════

def make_system_row(idx: int) -> dict:
    """System log row: LLM-only columns are null."""
    ts       = rand_ts(START_DATE, END_DATE)
    req_ts   = ts - timedelta(milliseconds=random.randint(1, 500))
    region   = random.choice(regions)
    app      = random.choice(applications)
    src_type = random.choice(source_types)
    log_type = weighted_log_type()
    env      = random.choice(environments)
    service  = random.choice(services)
    method   = random.choice(http_methods)
    ct       = random.choice(content_types)
    host     = f"{region['region_code'].lower()}.sap-services.internal"
    path     = rand_path(app["id"], src_type)
    msg      = sys_message(log_type, app["id"], src_type)
    ehash    = sha256(f"{ts.isoformat()}{app['id']}{src_type}{idx}")

    row = empty_row()
    row.update({
        "_id":                          str(uuid.uuid4()),
        "_ignored":                     "",
        "_index":                       f"sap-logs-{ts.strftime('%Y.%m')}",
        "_score":                       round(random.uniform(0.5, 1.0), 4),
        "@timestamp":                   iso(ts),
        "@version":                     "1",
        "event_code_version":           f"{random.randint(1,3)}.{random.randint(0,9)}.{random.randint(0,9)}",
        "event_hash":                   ehash,
        "@event_time_requested":        iso(req_ts),
        "headers_content_type":         ct,
        "headers_http_host":            host,
        "headers_http_request_method":  method,
        "heathers_request_path":        path,
        "sap_function_application":     app["id"],
        "sap_source_type":              src_type,
        "sap_function_log_type":        log_type,
        "sap_function_message":         msg,
        "sap_app_env":                  env,
        # sap_llm_response_size / time → null for system logs
        "sap_llm_response_size":        "",
        "sap_llm_response_time":        "",
        # region
        "region_id":                    region["region_id"],
        "region_name":                  region["region_name"],
        "region_code":                  region["region_code"],
        "macro_region":                 region["macro_region"],
        # system-only
        "service_id":                   service["id"],
        "http_status_code":             http_status_for_log_type(log_type),
        "client_ip":                    rand_ip(log_type),
        # LLM-only → all remain ""
    })
    return row


def make_llm_row(idx: int) -> dict:
    """LLM log row: system-only columns (service_id, http_status_code, client_ip) are null."""
    ts       = rand_ts(START_DATE, END_DATE)
    req_ts   = ts - timedelta(milliseconds=random.randint(50, 2000))
    region   = random.choice(regions)
    app      = random.choice(applications)
    src_type = random.choice(source_types)
    env      = random.choice(environments)
    model    = random.choice(llm_models)
    method   = random.choice(http_methods)
    ct       = random.choice(content_types)
    host     = f"llm.{region['region_code'].lower()}.sap-ai.internal"

    # LLM log sub-type
    llm_log_type = random.choices(
        list(LLM_LOG_TYPE_WEIGHTS.keys()),
        weights=list(LLM_LOG_TYPE_WEIGHTS.values())
    )[0]

    prompt_tok    = random.randint(*LLM_PROMPT_TOKENS_RANGE)
    comp_tok      = random.randint(*LLM_COMPLETION_TOKENS_RANGE)
    total_tok     = prompt_tok + comp_tok
    resp_time_ms  = round(random.uniform(*LLM_RESPONSE_TIME_RANGE_MS), 2)
    resp_size     = random.randint(*LLM_RESPONSE_SIZE_RANGE)
    temperature   = round(random.uniform(*LLM_TEMPERATURE_RANGE), 2)
    top_p         = round(random.uniform(*LLM_TOP_P_RANGE), 2)
    stream        = random.choice([True, False])
    cost          = round(model["cost_per_1k_tokens"] * total_tok / 1000, 6)
    ehash         = sha256(f"{ts.isoformat()}{model['id']}{app['id']}{idx}")
    prompt_id, prompt_cat, prompt_text = rand_prompt(region["region_name"], app["id"])

    if llm_log_type == "LLM_ERROR":
        llm_status     = "error"
        finish_reason  = random.choice(["content_filter", "length"])
        error_msg      = random.choice(LLM_ERROR_MESSAGES)
        resp_size_val  = ""
        resp_time_val  = round(random.uniform(*LLM_ERROR_RESPONSE_TIME_MS), 2)
        sap_resp_size  = ""
        sap_resp_time  = resp_time_val
    elif llm_log_type == "LLM_TIMEOUT":
        llm_status     = "timeout"
        finish_reason  = "timeout"
        error_msg      = "Request timed out after 30 s."
        resp_size_val  = ""
        resp_time_val  = round(random.uniform(*LLM_TIMEOUT_RESPONSE_TIME_MS), 2)
        sap_resp_size  = ""
        sap_resp_time  = resp_time_val
    else:
        llm_status     = "success"
        finish_reason  = random.choices(
            list(LLM_FINISH_REASON_WEIGHTS.keys()),
            weights=list(LLM_FINISH_REASON_WEIGHTS.values())
        )[0]
        error_msg      = ""
        resp_size_val  = resp_size
        resp_time_val  = resp_time_ms
        sap_resp_size  = resp_size
        sap_resp_time  = resp_time_ms

    msg = (
        f"LLM {llm_status.upper()}: {model['id']} responded in {resp_time_val} ms "
        f"({total_tok} tokens) via {app['id']}."
    ) if not error_msg else (
        f"LLM {llm_status.upper()}: {error_msg} (model={model['id']}, app={app['id']})"
    )

    row = empty_row()
    row.update({
        "_id":                          str(uuid.uuid4()),
        "_ignored":                     "",
        "_index":                       f"llm-logs-{ts.strftime('%Y.%m')}",
        "_score":                       round(random.uniform(0.5, 1.0), 4),
        "@timestamp":                   iso(ts),
        "@version":                     "1",
        "event_code_version":           f"{random.randint(1,3)}.{random.randint(0,9)}.{random.randint(0,9)}",
        "event_hash":                   ehash,
        "@event_time_requested":        iso(req_ts),
        "headers_content_type":         ct,
        "headers_http_host":            host,
        "headers_http_request_method":  method,
        "heathers_request_path":        f"/api/llm/{app['id']}/completion",
        "sap_function_application":     app["id"],
        "sap_source_type":              src_type,
        "sap_function_log_type":        llm_log_type,
        "sap_function_message":         msg,
        "sap_app_env":                  env,
        "sap_llm_response_size":        sap_resp_size,
        "sap_llm_response_time":        sap_resp_time,
        # region
        "region_id":                    region["region_id"],
        "region_name":                  region["region_name"],
        "region_code":                  region["region_code"],
        "macro_region":                 region["macro_region"],
        # system-only → null for LLM rows
        "service_id":                   "",
        "http_status_code":             "",
        "client_ip":                    "",
        # LLM-only
        "llm_model_id":                 model["id"],
        "llm_provider":                 model["provider"],
        "llm_prompt_id":                prompt_id,
        "llm_prompt_category":          prompt_cat,
        "llm_prompt":                   prompt_text,
        "llm_prompt_tokens":            prompt_tok,
        "llm_completion_tokens":        comp_tok,
        "llm_total_tokens":             total_tok,
        "llm_response_time_ms":         resp_time_val,
        "llm_response_size_bytes":      resp_size_val,
        "llm_status":                   llm_status,
        "llm_error_message":            error_msg,
        "llm_cost_usd":                 cost,
        "llm_temperature":              temperature,
        "llm_top_p":                    top_p,
        "llm_stream":                   stream,
        "llm_finish_reason":            finish_reason,
    })
    return row


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print(f"Generating {N_ROWS:,} rows  ({PCT_SYSTEM*100:.0f}% system / {(1-PCT_SYSTEM)*100:.0f}% LLM) …")

    n_system = int(N_ROWS * PCT_SYSTEM)
    n_llm    = N_ROWS - n_system

    rows = []
    for i in range(n_system):
        rows.append(make_system_row(i))
    for i in range(n_llm):
        rows.append(make_llm_row(i))

    # Shuffle so system and LLM rows are interleaved
    random.shuffle(rows)

    out_path = os.path.join(OUTPUT_DIR, "logs.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    # ── summary ───────────────────────────────────────────────────────────────
    log_type_counts: dict[str, int] = {}
    for r in rows:
        lt = r["sap_function_log_type"]
        log_type_counts[lt] = log_type_counts.get(lt, 0) + 1

    print(f"\n✅  {out_path}")
    print(f"   Total rows : {len(rows):>6,}")
    print(f"   Columns    : {len(COLUMNS)}")
    print("\n   Log type distribution:")
    for lt, cnt in sorted(log_type_counts.items(), key=lambda x: -x[1]):
        is_llm = lt.startswith("LLM")
        null_note = "(system-only cols null)" if is_llm else "(LLM-only cols null)"
        print(f"     {lt:<18} {cnt:>5}  {null_note}")


if __name__ == "__main__":
    main()