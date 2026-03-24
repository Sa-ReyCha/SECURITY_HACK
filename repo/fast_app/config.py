"""
config.py
---------
All tunable API settings loaded from environment variables (or .env file).

BATCH_SIZE       – rows returned per page (server-side, not per-call)
API_KEYS_PATH    – JSON file mapping bearer-token → team name
ACCESS_LOG_PATH  – CSV file where every authenticated request is appended
CSV_PATH         – path to the logs CSV (relative to fast_app/ or absolute)
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Single shared instance – import this everywhere
settings = Settings()