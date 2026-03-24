# Configuration Reference

## Files

| File | Purpose | Hot-reload? |
|---|---|---|
| `fast_app/.env` | Runtime settings (batch size, rate limits, paths) | Yes — restart container, no rebuild |
| `fast_app/api_keys.json` | Token → team_name mapping | Yes — restart container, no rebuild |
| `fast_app/config.py` | Pydantic-settings class (reads `.env`) | No — code change requires rebuild |
| `podman-compose.yml` | Container orchestration | No — requires `up -d` |

## .env variables

```ini
# Rows returned per page in /logs/current
BATCH_SIZE=500

# Max requests per 30-minute window per token (0 = disabled)
MAX_REQUESTS_PER_WINDOW=200

# How long to block a token after exceeding the limit (minutes)
BLOCK_DURATION_MINUTES=10

# Path to the main data CSV (relative to /app inside container)
CSV_PATH=output/logs.csv

# Path where access logs are written (relative to /app inside container)
ACCESS_LOG_PATH=output/access_logs.csv

# Path to the API keys JSON file (relative to /app inside container)
API_KEYS_PATH=api_keys.json
```

## api_keys.json format

```json
{
  "<bearer_token>": "<team_display_name>",
  "santiadmin99":        "TestTeam",
  "UPAEP_TEAM_KEY_2026": "UPAEP_TEAM"
}
```

The token is what teams put in `Authorization: Bearer <token>`.
The team name is what appears in access logs and rate-limit messages.

## podman-compose.yml key settings

```yaml
services:
  api:
    healthcheck:
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 60s   # grace period for CSV load

  cloudflared:
    command: tunnel --no-autoupdate run --url http://api:8000
    environment:
      - TUNNEL_TOKEN=${TUNNEL_TOKEN}   # read from fast_app/.env or host env
```

## Volume

```bash
# Create (one-time setup)
podman volume create soc_api_output

# Pre-populate with data
podman run --rm \
  -v soc_api_output:/data \
  -v /path/to/logs.csv:/src/logs.csv:ro \
  alpine cp /src/logs.csv /data/logs.csv

# Inspect
podman volume inspect soc_api_output