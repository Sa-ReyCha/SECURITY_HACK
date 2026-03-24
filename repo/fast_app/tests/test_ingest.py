"""
tests/test_ingest.py
--------------------
Integration test / ingestion script.

Fetches ALL pages from GET /logs/current using one of the API keys defined in
api_keys.json, then saves the full result to tests/output/ingested_logs.csv.

Usage (from the fast_app/ directory):
    python tests/test_ingest.py

Requirements:
    - The FastAPI server must be running:  uvicorn main:app --reload --port 8000
    - api_keys.json must exist in fast_app/
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

# ── configuration ─────────────────────────────────────────────────────────────
# BASE_URL       = "http://localhost:8000"
BASE_URL       = "https://soc-api.840127.xyz"
API_KEYS_FILE  = Path(__file__).parent.parent / "api_keys.json"
OUTPUT_DIR     = Path(__file__).parent / "output"
OUTPUT_FILE    = OUTPUT_DIR / "ingested_logs.csv"

# Pick the first key from api_keys.json automatically
def _load_first_key() -> tuple[str, str]:
    """Returns (token, team_name) of the first entry in api_keys.json."""
    with open(API_KEYS_FILE, encoding="utf-8") as f:
        keys: dict[str, str] = json.load(f)
    token, team = next(iter(keys.items()))
    return token, team


# ── helpers ───────────────────────────────────────────────────────────────────
def check_health() -> None:
    """Assert the server is reachable before starting the ingestion loop."""
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        r.raise_for_status()
        print(f"[health] {r.json()}")
    except requests.exceptions.ConnectionError:
        print(
            f"\n❌  Cannot reach {BASE_URL}\n"
            "    Start the server first:\n"
            "      cd fast_app && uvicorn main:app --reload --port 8000\n"
        )
        sys.exit(1)


def fetch_config(headers: dict) -> dict:
    """Fetch config with retry logic for rate limiting."""
    max_retries = 3
    retry_delay = 1.0
    
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(f"{BASE_URL}/config", headers=headers, timeout=10)
            
            if r.status_code == 503 and _is_cloudflare_error(r):
                if attempt < max_retries:
                    print(f"[config] Rate limited (attempt {attempt}/{max_retries}), retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                    continue
                else:
                    cf_ray = r.headers.get("cf-ray", "N/A")
                    print(f"\n{'='*60}")
                    print(f"  ⚠️  HTTP 503 — Rate Limiting")
                    print(f"  Ray ID: {cf_ray}")
                    print(f"\n  Failed after {max_retries} retries.")
                    print(f"  Suggestion: Increase the delay between requests")
                    print(f"{'='*60}\n")
                    sys.exit(1)
            
            r.raise_for_status()
            cfg = r.json()
            print(f"[config] batch_size={cfg['batch_size']}  csv_path={cfg['csv_path']}")
            return cfg
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                print(f"[config] Error (attempt {attempt}/{max_retries}): {e}, retrying...")
                time.sleep(retry_delay)
                retry_delay *= 1.5
            else:
                raise


def _is_cloudflare_error(r: requests.Response) -> bool:
    """
    Detect if the 503 error is from Cloudflare (rate limiting).
    
    Cloudflare errors typically have:
    - Status: 503 or 429
    - Headers: cf-ray, cf-request-id, server: cloudflare
    - Body: HTML error page or JSON with Cloudflare details
    """
    if r.status_code in (429, 503):
        cf_ray = r.headers.get("cf-ray")
        cf_request_id = r.headers.get("cf-request-id")
        server = r.headers.get("server", "").lower()
        
        return bool(cf_ray or cf_request_id or "cloudflare" in server)
    return False


def _handle_response(r: requests.Response, page: int) -> dict:
    """
    Parse a response and raise a clean error on 4xx/5xx.
    For 429 specifically, prints the server's human-readable message.
    """
    if r.status_code == 429:
        retry_after = r.headers.get("Retry-After", "?")
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        print(f"\n{'='*60}")
        print(f"  HTTP 429 — Too Many Requests  (page {page})")
        print(f"  Retry-After: {retry_after}s")
        print(f"\n  Server message:\n")
        for line in detail.split(". "):
            print(f"    {line.strip()}")
        print(f"{'='*60}\n")
        sys.exit(1)

    if r.status_code == 503 and _is_cloudflare_error(r):
        cf_ray = r.headers.get("cf-ray", "N/A")
        print(f"\n{'='*60}")
        print(f"  ⚠️  HTTP 503 — Rate Limiting (page {page})")
        print(f"  Ray ID: {cf_ray}")
        print(f"\n  Suggestion:")
        print(f"    1. Retry this page again")
        print(f"    2. If it fails again, increase the delay between requests")
        print(f"       Edit the time.sleep(1.0) value in the ingest_all_pages function")
        print(f"{'='*60}\n")
        sys.exit(1)

    r.raise_for_status()
    return r.json()


def ingest_all_pages(headers: dict) -> list[dict]:
    """
    Fetches every page of /logs/current and returns the combined records list.
    """
    all_records: list[dict] = []

    # ── page 1 ────────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    r = requests.get(
        f"{BASE_URL}/logs/current",
        headers=headers,
        params={"page": 1},
        timeout=30,
    )
    payload = _handle_response(r, page=1)

    total_pages   = payload["total_pages"]
    total_records = payload["total_records"]
    window_start  = payload["window_start"]
    window_end    = payload["window_end"]
    req_time_utc  = payload["request_time_utc"]

    print(f"\n[window]  {window_start}  →  {window_end}")
    print(f"[utc]     request_time_utc = {req_time_utc}")
    print(f"[total]   {total_records:,} records across {total_pages} page(s)\n")

    all_records.extend(payload["data"])
    print(f"  page  1 / {total_pages}  — {len(payload['data'])} records", flush=True)

    # ── pages 2 … N ───────────────────────────────────────────────────────────
    for page in range(2, total_pages + 1):
        # Add delay between requests to avoid Cloudflare rate limiting
        time.sleep(1.0)
        
        r = requests.get(
            f"{BASE_URL}/logs/current",
            headers=headers,
            params={"page": page},
            timeout=30,
        )
        data = _handle_response(r, page=page)["data"]
        all_records.extend(data)
        print(f"  page {page:>3} / {total_pages}  — {len(data)} records", flush=True)

    elapsed = time.perf_counter() - t0
    print(f"\n[done]  {len(all_records):,} records fetched in {elapsed:.2f}s")
    return all_records


def main() -> None:
    """Main ingestion workflow."""
    check_health()

    token, team = _load_first_key()
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[auth]    Using token for: {team}")

    fetch_config(headers)

    records = ingest_all_pages(headers)

    # ── save to CSV ───────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(records)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"\n✅  Saved {len(df):,} rows × {len(df.columns)} columns")
    print(f"   → {OUTPUT_FILE.resolve()}")

    # ── quick summary ─────────────────────────────────────────────────────────
    if "sap_function_log_type" in df.columns:
        print("\n   Log type distribution:")
        for lt, cnt in df["sap_function_log_type"].value_counts().items():
            print(f"     {lt:<20} {cnt:>6,}")


if __name__ == "__main__":
    main()
