"""
main.py
-------
FastAPI application that serves SAP SOC log data.
"""

from __future__ import annotations

import asyncio
import csv
import json
import math
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import settings

# ── data store ────────────────────────────────────────────────────────────────
_df: pd.DataFrame | None = None
_api_keys: dict[str, str] = {}       # token → team_name
_access_log_lock: asyncio.Lock | None = None  # protects concurrent CSV writes

# ── rate limiter state ────────────────────────────────────────────────────────
@dataclass
class _RateBucket:
    window_start: datetime
    count: int = 0
    blocked_until: datetime | None = None   # set when penalty is active

_rate_buckets: dict[str, _RateBucket] = {}   # token → bucket
_rate_limit_lock: asyncio.Lock | None = None  # protects _rate_buckets

# ── access-log CSV columns ────────────────────────────────────────────────────
_ACCESS_LOG_COLS = [
    "timestamp_utc",
    "team_name",
    "api_key_prefix",
    "endpoint",
    "http_method",
    "page",
    "http_status_code",
    "records_returned",
    "window_start",
    "window_end",
    "latency_ms",
]


def _init_access_log() -> None:
    """Create the access-log CSV with headers if it does not yet exist."""
    path = settings.access_log_path
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_ACCESS_LOG_COLS)
            writer.writeheader()


async def _write_access_log(row: dict[str, Any]) -> None:
    """Append one row to the access-log CSV, serialised via asyncio.Lock."""
    async with _access_log_lock:  # type: ignore[union-attr]
        with open(settings.access_log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_ACCESS_LOG_COLS)
            writer.writerow(row)


# ── lifespan ──────────────────────────────────────────────────────────────────
async def _check_rate_limit(token: str, team_name: str, now_utc: datetime) -> None:
    """
    Increment the request counter for this token in the current 30-min window.

    Flow:
      1. If the key is currently in a penalty block → reject immediately (HTTP 429).
      2. If the window changed since the last request → reset the counter.
      3. Increment the counter.
      4. If the counter exceeds the limit → impose a BLOCK_DURATION_MINUTES penalty.

    Does nothing if MAX_REQUESTS_PER_WINDOW == 0 (rate limiting disabled).
    """
    limit = settings.max_requests_per_window
    if limit == 0:
        return

    penalty_minutes = settings.block_duration_minutes

    async with _rate_limit_lock:  # type: ignore[union-attr]
        bucket = _rate_buckets.get(token)

        # ── 1. Active penalty block? ──────────────────────────────────────────
        if bucket is not None and bucket.blocked_until is not None:
            if now_utc < bucket.blocked_until:
                remaining_s = int((bucket.blocked_until - now_utc).total_seconds()) + 1
                remaining_m = round(remaining_s / 60, 1)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"🚫 Team '{team_name}' is currently blocked due to excessive requests. "
                        f"Your API key exceeded the limit of {settings.max_requests_per_window} "
                        f"requests per 30-minute window. "
                        f"Please try again in approximately {remaining_m} minute(s). "
                        f"Your key will be unblocked at "
                        f"{bucket.blocked_until.strftime('%H:%M:%S UTC')} "
                        f"({bucket.blocked_until.isoformat()}). "
                        f"Tip: avoid infinite loops — a single ingestion needs only "
                        f"{settings.max_requests_per_window // 2} requests at most."
                    ),
                    headers={"Retry-After": str(remaining_s)},
                )
            else:
                # Penalty expired → clear it and reset counter
                bucket.blocked_until = None
                bucket.count = 0

        # ── 2. Compute current 30-min window start ────────────────────────────
        floored = 0 if now_utc.minute < 30 else 30
        current_window = now_utc.replace(minute=floored, second=0, microsecond=0)

        # ── 3. New key or new window → reset bucket ───────────────────────────
        if bucket is None or bucket.window_start != current_window:
            _rate_buckets[token] = _RateBucket(window_start=current_window, count=1)
            return

        # ── 4. Increment and check ────────────────────────────────────────────
        bucket.count += 1

        if bucket.count > limit:
            if penalty_minutes > 0:
                # Fixed-duration penalty
                unblock_at = now_utc + timedelta(minutes=penalty_minutes)
                bucket.blocked_until = unblock_at
                retry_after = penalty_minutes * 60 + 1
                detail = (
                    f"🚫 Team '{team_name}' has been temporarily blocked. "
                    f"Your API key made more than {limit} requests within a single "
                    f"30-minute data window, which exceeds the allowed limit. "
                    f"As a result, your key has been blocked for {penalty_minutes} minute(s). "
                    f"Please wait and try again after {unblock_at.strftime('%H:%M:%S UTC')} "
                    f"({unblock_at.isoformat()}). "
                    f"Remember: each team is allowed up to {limit} requests per 30-minute window. "
                    f"Avoid infinite loops — one full ingestion requires {limit // 2} requests at most."
                )
            else:
                # Fall back to window-reset behaviour
                next_window = current_window + timedelta(minutes=30)
                retry_after = int((next_window - now_utc).total_seconds()) + 1
                detail = (
                    f"🚫 Team '{team_name}' has been temporarily blocked. "
                    f"Your API key made more than {limit} requests within the current "
                    f"30-minute data window, which exceeds the allowed limit. "
                    f"Please wait until the next window opens at "
                    f"{next_window.strftime('%H:%M:%S UTC')} ({next_window.isoformat()}). "
                    f"Remember: each team is allowed up to {limit} requests per 30-minute window."
                )

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail,
                headers={"Retry-After": str(retry_after)},
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _df, _api_keys, _access_log_lock, _rate_limit_lock
    _access_log_lock = asyncio.Lock()
    _rate_limit_lock = asyncio.Lock()

    # Load API keys
    print(f"[startup] Loading API keys from: {settings.api_keys_path}")
    with open(settings.api_keys_path, encoding="utf-8") as f:
        _api_keys = json.load(f)
    print(f"[startup] {len(_api_keys)} API key(s) registered: {list(_api_keys.values())}")

    # Initialise access log
    _init_access_log()
    print(f"[startup] Access log: {settings.access_log_path}")

    # Load main CSV
    print(f"[startup] Loading data from: {settings.csv_path}")
    _df = pd.read_csv(
        settings.csv_path,
        dtype=str,
        keep_default_na=False,
    )
    _df["_ts"] = pd.to_datetime(_df["@timestamp"], utc=True, errors="coerce")
    print(f"[startup] Loaded {len(_df):,} rows, {len(_df.columns)} columns.")
    yield
    print("[shutdown] Bye.")


# ── app ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SAP SOC Log Ingestion API",
    summary="Real-time SAP security log stream for AI-driven threat detection pipelines.",
    description="""
<img src="/static/API_Front_Page.png" alt="SAP SOC Log Ingestion API" style="width:100%;max-width:900px;border-radius:8px;margin-bottom:1.5rem;" />

## Context

This API is the **primary data source** for the SAP Security Operations Center (SOC) Hackathon.
It exposes a continuous stream of SAP system and LLM interaction logs that your team
must ingest, analyze, and act upon in real time.

Your pipeline is expected to:
1. **Ingest** log batches from this API on a rolling 30-minute window basis.
2. **Detect** security anomalies, behavioral shifts, and threat patterns using ML/AI models.
3. **Alert** SAP stakeholders via the notification system when threats are confirmed.
4. **Report** forensic findings with strategic hardening recommendations.

---

## Log Stream Architecture

Logs are generated continuously and split into two categories:

| Category | `sap_function_log_type` values | Key signal fields |
|---|---|---|
| **System** | `INFO` `WARNING` `ERROR` `DEBUG` `AUDIT` `PERF` `SECURITY` | `http_status_code`, `client_ip`, `service_id` |
| **LLM Interaction** | `LLM_REQUEST` `LLM_ERROR` `LLM_TIMEOUT` | `llm_model_id`, `llm_status`, `llm_cost_usd`, `llm_response_time_ms` |

> ⚠️ **Null pattern by design:** LLM log rows leave system-only columns empty
> (`service_id`, `http_status_code`, `client_ip`), and system log rows leave all
> `llm_*` columns empty. Your preprocessing pipeline must handle this correctly.

---

## Time Window

The API always returns data for the **current UTC 30-minute slot** — no date parameters needed.
The server computes the window from its own clock at request time:

| Server UTC minute | Window served |
|---|---|
| **00 – 29** | `HH:00:00 → HH:30:00` (exclusive) |
| **30 – 59** | `HH:30:00 → HH+1:00:00` (exclusive) |

This mirrors a real SOC ingestion cadence: your pipeline should poll this endpoint
periodically and process each batch as it arrives.

---

<details>
<summary><strong>Pagination</strong> — click to expand</summary>

The server controls batch size via the `BATCH_SIZE` configuration variable.
**Clients do not set the page size** — only the page number.

**Recommended ingestion loop:**

```python
import requests

TOKEN   = "your-bearer-token"
BASE    = "http://<host>:8000"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# 1. Fetch page 1 to discover total_pages
r = requests.get(f"{BASE}/logs/current", headers=HEADERS, params={"page": 1})
payload = r.json()

all_records = payload["data"]
for page in range(2, payload["total_pages"] + 1):
    r = requests.get(f"{BASE}/logs/current", headers=HEADERS, params={"page": page})
    all_records.extend(r.json()["data"])

# 2. Feed all_records into your Pandas / ML pipeline
import pandas as pd
df = pd.DataFrame(all_records)
```

</details>

---

<details>
<summary><strong>Authentication</strong> — click to expand</summary>

All endpoints except `/health` require a **Bearer token** in the `Authorization` header:

```
Authorization: Bearer <your-team-token>
```

Tokens are distributed per team at the start of the hackathon.
Contact the technical staff if your token is rejected.

</details>

---

<details>
<summary><strong>Role Guidance</strong> — click to expand</summary>

| Role | Relevant endpoints & fields |
|---|---|
| **AI & Data Science** | `/logs/current` → all columns; focus on `sap_function_log_type`, `http_status_code`, `client_ip`, `llm_status` for feature engineering |
| **Cloud Integration Engineer** | `/health` for probe checks; `/config` to verify batch size before deploying consumers on Cloud Foundry |
| **Data Architect / Backend** | Ingest `data[]` arrays directly into SAP HANA; use `_id` as primary key and `@timestamp` for time-series partitioning |
| **Security Analyst** | Filter `sap_function_log_type = SECURITY` and `ERROR`; correlate `client_ip` with `http_status_code` patterns |

</details>
""",
    version="1.0.0",
    contact={
        "name": "SEC HACK — Technical Staff",
        "email": "soc-hack@sap-hackathon.io",
    },
    license_info={
        "name": "Internal Use — Hackathon Only",
    },
    openapi_tags=[
        {
            "name": "logs",
            "description": (
                "Core ingestion endpoints. "
                "Use `GET /logs/current` as the entry point for your AI pipeline — "
                "poll it every 30 minutes to keep your detection models fed with fresh data."
            ),
        },
        {
            "name": "meta",
            "description": (
                "Operational endpoints. "
                "`/health` is suitable for Cloud Foundry liveness probes. "
                "`/config` lets you verify the server-side batch size before sizing your ingestion workers."
            ),
        },
    ],
    lifespan=lifespan,
)

# ── security scheme ───────────────────────────────────────────────────────────
_bearer_scheme = HTTPBearer(
    scheme_name="BearerToken",
    description="Paste your token — the `Bearer ` prefix is added automatically by this UI.",
)


# ── auth dataclass ─────────────────────────────────────────────────────────────
@dataclass
class TeamInfo:
    team_name: str
    api_key: str

    @property
    def api_key_prefix(self) -> str:
        """First 8 characters of the token — safe to log."""
        return self.api_key[:8] if len(self.api_key) >= 8 else self.api_key


# ── response models ───────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"], description="Always `ok` when the server is up.")


class ConfigResponse(BaseModel):
    batch_size: int = Field(
        ...,
        examples=[500],
        description="Number of rows returned per page (set via `BATCH_SIZE` env var).",
    )
    csv_path: str = Field(
        ...,
        examples=["../output/logs.csv"],
        description="Path to the CSV file loaded at startup.",
    )


class LogsResponse(BaseModel):
    request_time_utc: str = Field(
        ...,
        examples=["2026-03-18T12:17:43.521042+00:00"],
        description=(
            "Exact UTC timestamp of the server clock at the moment this request was processed. "
            "All window calculations are derived from this value."
        ),
    )
    window_start: str = Field(
        ...,
        examples=["2026-03-18T12:00:00+00:00"],
        description="ISO-8601 UTC start of the current 30-minute window (inclusive).",
    )
    window_end: str = Field(
        ...,
        examples=["2026-03-18T12:30:00+00:00"],
        description="ISO-8601 UTC end of the current 30-minute window (exclusive).",
    )
    total_records: int = Field(
        ...,
        examples=[54832],
        description="Total rows in the dataset that fall within this window.",
    )
    batch_size: int = Field(
        ...,
        examples=[500],
        description="Server-configured rows per page.",
    )
    current_page: int = Field(..., examples=[1], description="The page number returned.")
    total_pages: int = Field(..., examples=[110], description="Total number of pages available.")
    records_in_page: int = Field(
        ...,
        examples=[500],
        description="Number of rows actually included in `data` (may be less than `batch_size` on the last page).",
    )
    data: list[dict[str, Any]] = Field(
        ...,
        description="Log rows for this page. Column presence depends on `sap_function_log_type` — see overview.",
    )


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Human-readable error message.")


# ── auth dependency ────────────────────────────────────────────────────────────
def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> TeamInfo:
    """
    Validates the Bearer token against api_keys.json.
    Returns a TeamInfo with the resolved team name.
    """
    token = credentials.credentials
    team_name = _api_keys.get(token)
    if team_name is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TeamInfo(team_name=team_name, api_key=token)


# ── helpers ───────────────────────────────────────────────────────────────────
def current_half_hour_window() -> tuple[datetime, datetime, datetime]:
    """
    Return (now_utc, window_start, window_end) based strictly on the UTC clock.
    The server timezone is irrelevant — datetime.now(timezone.utc) is always UTC.
    """
    now = datetime.now(timezone.utc)
    floored_minute = 0 if now.minute < 30 else 30
    start = now.replace(minute=floored_minute, second=0, microsecond=0)
    end = start + timedelta(minutes=30)
    return now, start, end


def paginate(df: pd.DataFrame, page: int, batch_size: int) -> dict[str, Any]:
    total_records = len(df)
    total_pages = max(1, math.ceil(total_records / batch_size))

    if page > total_pages:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Page {page} is out of range. "
                f"Valid range: 1 – {total_pages} "
                f"(total records in window: {total_records})."
            ),
        )

    start_idx = (page - 1) * batch_size
    end_idx = start_idx + batch_size
    slice_df = df.iloc[start_idx:end_idx].drop(columns=["_ts"], errors="ignore")

    return {
        "total_records": total_records,
        "batch_size": batch_size,
        "current_page": page,
        "total_pages": total_pages,
        "records_in_page": len(slice_df),
        "data": slice_df.to_dict(orient="records"),
    }


# ── routes ────────────────────────────────────────────────────────────────────
@app.get(
    "/health",
    tags=["meta"],
    summary="Liveness probe",
    response_model=HealthResponse,
    responses={200: {"description": "Server is up and running."}},
)
def health() -> HealthResponse:
    """Returns `{"status": "ok"}` — no authentication required."""
    return HealthResponse(status="ok")


@app.get(
    "/config",
    tags=["meta"],
    summary="Show active server configuration",
    response_model=ConfigResponse,
    responses={
        200: {"description": "Current server-side configuration."},
        401: {"model": ErrorResponse, "description": "Missing or invalid Bearer token."},
    },
)
async def get_config(
    request: Request,
    team: TeamInfo = Depends(verify_token),
) -> ConfigResponse:
    """
    Returns the server-side configuration that is **not** controllable per-request:

    - **batch_size** – rows returned per page (set via `BATCH_SIZE` env var)
    - **csv_path** – path to the CSV file loaded at startup
    """
    await _write_access_log({
        "timestamp_utc":   datetime.now(timezone.utc).isoformat(),
        "team_name":       team.team_name,
        "api_key_prefix":  team.api_key_prefix,
        "endpoint":        "/config",
        "http_method":     request.method,
        "page":            "",
        "http_status_code": 200,
        "records_returned": "",
        "window_start":    "",
        "window_end":      "",
        "latency_ms":      "",
    })
    return ConfigResponse(batch_size=settings.batch_size, csv_path=settings.csv_path)


@app.get(
    "/logs/current",
    tags=["logs"],
    summary="Get logs for the current 30-minute window",
    response_model=LogsResponse,
    responses={
        200: {"description": "Paginated log rows for the current half-hour window."},
        401: {"model": ErrorResponse, "description": "Missing or invalid Bearer token."},
        422: {"model": ErrorResponse, "description": "Requested page is out of range."},
        503: {"model": ErrorResponse, "description": "Data not loaded yet."},
    },
)
async def get_current_logs(
    request: Request,
    page: int = Query(
        default=1,
        ge=1,
        description=(
            "Page number to retrieve (1-based). "
            "Use `total_pages` from a previous response to know how many pages exist."
        ),
        examples=[1],
    ),
    team: TeamInfo = Depends(verify_token),
) -> LogsResponse:
    """
    Returns log rows whose **`@timestamp`** falls within the **current UTC 30-minute window**,
    delivered as one page of a server-configured batch.

    ### Window calculation (server UTC clock)

    | Current minute | Window |
    |---|---|
    | 00 – 29 | `HH:00 → HH:30` |
    | 30 – 59 | `HH:30 → HH+1:00` |

    ### Pagination workflow

    1. Call `GET /logs/current` (no `page` param) → inspect `total_pages` in the response.
    2. Iterate `?page=1` … `?page=N` to retrieve all batches.
    3. Page size is fixed server-side (`BATCH_SIZE`); use `GET /config` to check the current value.

    ### Null patterns in the data

    | `sap_function_log_type` | Empty columns |
    |---|---|
    | System types (`INFO`, `ERROR`, …) | All `llm_*` columns |
    | LLM types (`LLM_REQUEST`, …) | `service_id`, `http_status_code`, `client_ip` |
    """
    if _df is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Data not loaded yet. Please retry shortly.",
        )

    t_start = time.perf_counter()
    now_utc, window_start, window_end = current_half_hour_window()

    # ── rate limit check ──────────────────────────────────────────────────────
    try:
        await _check_rate_limit(team.api_key, team.team_name, now_utc)
    except HTTPException as exc:
        # Log the blocked request before re-raising
        await _write_access_log({
            "timestamp_utc":    now_utc.isoformat(),
            "team_name":        team.team_name,
            "api_key_prefix":   team.api_key_prefix,
            "endpoint":         "/logs/current",
            "http_method":      request.method,
            "page":             page,
            "http_status_code": 429,
            "records_returned": 0,
            "window_start":     window_start.isoformat(),
            "window_end":       window_end.isoformat(),
            "latency_ms":       round((time.perf_counter() - t_start) * 1000, 2),
        })
        raise

    mask = (_df["_ts"] >= window_start) & (_df["_ts"] < window_end)
    filtered = _df.loc[mask].reset_index(drop=True)

    envelope = paginate(filtered, page, settings.batch_size)

    latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

    envelope["request_time_utc"] = now_utc.isoformat()
    envelope["window_start"] = window_start.isoformat()
    envelope["window_end"] = window_end.isoformat()

    # ── write access log ──────────────────────────────────────────────────────
    await _write_access_log({
        "timestamp_utc":    now_utc.isoformat(),
        "team_name":        team.team_name,
        "api_key_prefix":   team.api_key_prefix,
        "endpoint":         "/logs/current",
        "http_method":      request.method,
        "page":             page,
        "http_status_code": 200,
        "records_returned": envelope["records_in_page"],
        "window_start":     window_start.isoformat(),
        "window_end":       window_end.isoformat(),
        "latency_ms":       latency_ms,
    })

    return envelope


# ── static files (cover image served for Swagger UI) ─────────────────────────
app.mount("/static", StaticFiles(directory="img"), name="static")