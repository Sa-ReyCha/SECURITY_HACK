"""
config.py
---------
All tunable API settings loaded from environment variables (or .env file).

BATCH_SIZE                  – rows returned per page (server-side, not per-call)
API_KEYS_PATH               – JSON file mapping bearer-token → team name
ACCESS_LOG_PATH             – CSV file where every authenticated request is appended
CSV_PATH                    – path to the logs CSV (relative to fast_app/ or absolute)

OpenSearch settings (all optional — leave OPENSEARCH_HOST empty to disable):
OPENSEARCH_HOST             – full URL, e.g. https://opensearch.993212.xyz
OPENSEARCH_USER             – HTTP basic-auth username
OPENSEARCH_PASSWORD         – HTTP basic-auth password
OPENSEARCH_INDEX            – index name to write access-log documents into
OPENSEARCH_MAX_RETRIES      – how many times to retry a failed index call
OPENSEARCH_RETRY_DELAY_S    – base delay (seconds) for exponential back-off
OPENSEARCH_FALLBACK_CSV     – CSV written when all retries are exhausted
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Number of rows returned per page / batch
    batch_size: int = 500

    # Path to the JSON file that maps bearer tokens to team names
    api_keys_path: str = "api_keys.json"

    # Path to the access-log CSV (relative to /app inside the container)
    access_log_path: str = "output/access_logs.csv"

    # Max authenticated requests per 30-minute window per API key.
    # A full ingestion (110 pages) uses 110 requests; set higher to allow retries.
    # Set to 0 to disable rate limiting.
    max_requests_per_window: int = 220

    # How many minutes to block a key once it exceeds max_requests_per_window.
    # The block is a hard penalty timer — independent of the 30-min data window.
    # Set to 0 to use window-reset behaviour instead.
    block_duration_minutes: int = 10

    # Path to the logs CSV produced by generate_synthetic_data.py
    csv_path: str = "output/logs.csv"

    # ── OpenSearch integration (leave opensearch_host="" to disable) ───────────
    # Full URL of the OpenSearch endpoint, e.g. https://opensearch.993212.xyz
    opensearch_host: str = ""

    # HTTP basic-auth credentials
    opensearch_user: str = ""
    opensearch_password: str = ""

    # Index name where access-log documents are written
    opensearch_index: str = "access_logs"

    # Retry policy for failed index calls
    opensearch_max_retries: int = 3
    opensearch_retry_delay_s: float = 1.0

    # Fallback CSV — written when all retries are exhausted
    opensearch_fallback_csv: str = "output/opensearch_failed.csv"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Single shared instance – import this everywhere
settings = Settings()