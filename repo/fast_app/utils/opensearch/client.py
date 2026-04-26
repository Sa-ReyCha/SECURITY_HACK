"""
utils/opensearch/client.py
--------------------------
Async helper that indexes an access-log row into OpenSearch.

Behaviour
---------
* If OPENSEARCH_HOST is empty the function is a no-op (feature disabled).
* The OpenSearch client is created once (module-level singleton) and reused.
* Retries: up to ``settings.opensearch_max_retries`` attempts with
  exponential back-off (``retry_delay_s * 2^attempt`` seconds).
* Fallback: when all retries are exhausted the row is appended to
  ``settings.opensearch_fallback_csv`` so no record is silently lost.

Usage (from main.py)
--------------------
    from utils.opensearch.client import index_access_log
    asyncio.create_task(index_access_log(row))
"""

from __future__ import annotations

import asyncio
import csv
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ── lazy singleton ─────────────────────────────────────────────────────────────
_os_client = None  # opensearch.OpenSearch instance, created on first use


def _get_client():
    """Return (and lazily create) the module-level OpenSearch client."""
    global _os_client
    if _os_client is not None:
        return _os_client

    # Import here so the module can be imported even if opensearch-py is not
    # installed yet (e.g. during local development without the package).
    try:
        from opensearchpy import OpenSearch  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "opensearch-py is not installed. "
            "Add 'opensearch-py>=2.4.0' to requirements.txt and rebuild."
        ) from exc

    from config import settings  # local import to avoid circular deps at module load

    if not settings.opensearch_host:
        return None  # feature disabled

    _os_client = OpenSearch(
        hosts=[settings.opensearch_host],
        http_auth=(settings.opensearch_user, settings.opensearch_password),
        use_ssl=settings.opensearch_host.startswith("https"),
        verify_certs=True,
        ssl_show_warn=False,
    )
    logger.info("[opensearch] Client initialised → %s", settings.opensearch_host)
    print(f"[opensearch] Client initialised → {settings.opensearch_host}", flush=True)
    return _os_client


# ── fallback CSV ───────────────────────────────────────────────────────────────
_FALLBACK_COLS = [
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
    "error",
]


def _write_fallback(row: dict[str, Any], error: str) -> None:
    """Append *row* (plus the error message) to the fallback CSV."""
    from config import settings  # local import

    path = settings.opensearch_fallback_csv
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FALLBACK_COLS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow({**row, "error": error})

    logger.warning("[opensearch] Fallback CSV written → %s | error: %s", path, error)
    print(
        f"[opensearch] FALLBACK team={row.get('team_name', '-')} "
        f"endpoint={row.get('endpoint', '-')} "
        f"→ {path} | error: {error}",
        flush=True,
    )


# ── public async entry-point ───────────────────────────────────────────────────

async def index_access_log(row: dict[str, Any]) -> None:
    """
    Index *row* into OpenSearch with retry + CSV fallback.

    This coroutine is designed to be launched as a fire-and-forget task::

        asyncio.create_task(index_access_log(row))

    It never raises — all errors are logged and/or written to the fallback CSV.
    """
    from config import settings  # local import

    if not settings.opensearch_host:
        return  # feature disabled — nothing to do

    max_retries: int = settings.opensearch_max_retries
    base_delay: float = settings.opensearch_retry_delay_s
    index_name: str = settings.opensearch_index

    last_error: str = ""

    for attempt in range(max_retries):
        try:
            # Run the blocking OpenSearch call in a thread pool so we don't
            # stall the FastAPI event loop.
            await asyncio.to_thread(_index_sync, index_name, row)
            logger.debug(
                "[opensearch] Indexed OK (attempt %d/%d) → %s",
                attempt + 1,
                max_retries,
                index_name,
            )
            print(
                f"[opensearch] OK "
                f"team={row.get('team_name', '-')} "
                f"endpoint={row.get('endpoint', '-')} "
                f"status={row.get('http_status_code', '-')} "
                f"attempt={attempt + 1}/{max_retries} "
                f"index={index_name}",
                flush=True,
            )
            return  # ✓ success

        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "[opensearch] Attempt %d/%d failed: %s",
                attempt + 1,
                max_retries,
                last_error,
            )
            if attempt < max_retries - 1:
                sleep_s = base_delay * (2 ** attempt)
                logger.debug("[opensearch] Retrying in %.1fs …", sleep_s)
                print(
                    f"[opensearch] RETRY {attempt + 1}/{max_retries} "
                    f"team={row.get('team_name', '-')} "
                    f"in {sleep_s:.1f}s | {last_error}",
                    flush=True,
                )
                await asyncio.sleep(sleep_s)
            else:
                print(
                    f"[opensearch] FAILED {attempt + 1}/{max_retries} "
                    f"team={row.get('team_name', '-')} | {last_error}",
                    flush=True,
                )

    # All retries exhausted → write to fallback CSV
    logger.error(
        "[opensearch] All %d retries exhausted. Writing to fallback CSV.", max_retries
    )
    _write_fallback(row, last_error)


def _index_sync(index_name: str, row: dict[str, Any]) -> None:
    """Blocking helper — called via asyncio.to_thread."""
    client = _get_client()
    if client is None:
        return  # feature disabled (race condition guard)
    client.index(index=index_name, body=row)