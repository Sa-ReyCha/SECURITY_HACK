# Data Reference

## Main Dataset: logs.csv

- **Location inside container:** `/app/output/logs.csv` (in named volume `soc_api_output`)
- **Location on host volume:** `/Users/santi/.local/share/containers/storage/volumes/soc_api_output/_data/logs.csv`
- **Size:** 1,220,600 rows × 45 columns
- **Load time:** ~10-15 seconds at container startup
- **Format:** CSV, all columns as strings (`dtype=str`, `keep_default_na=False`)

### Key columns

| Column | Type | Description |
|---|---|---|
| `_id` | string | Unique row identifier (use as primary key) |
| `@timestamp` | ISO-8601 UTC | Log event time — used for window filtering |
| `sap_function_log_type` | enum | Log category (see below) |
| `http_status_code` | string | HTTP status (system logs only) |
| `client_ip` | string | Client IP (system logs only) |
| `service_id` | string | SAP service (system logs only) |
| `llm_model_id` | string | LLM model name (LLM logs only) |
| `llm_status` | string | LLM call status (LLM logs only) |
| `llm_cost_usd` | string | LLM cost (LLM logs only) |
| `llm_response_time_ms` | string | LLM latency (LLM logs only) |

### Log types

| `sap_function_log_type` | Category | Empty columns |
|---|---|---|
| `INFO`, `WARNING`, `ERROR`, `DEBUG`, `AUDIT`, `PERF`, `SECURITY` | System | All `llm_*` columns |
| `LLM_REQUEST`, `LLM_ERROR`, `LLM_TIMEOUT` | LLM Interaction | `service_id`, `http_status_code`, `client_ip` |

### Window distribution

The dataset covers multiple 30-minute UTC windows. At any given time, the API serves
the window matching the current UTC clock (HH:00–HH:30 or HH:30–HH+1:00).
Typical window size: ~5,000–6,000 rows → ~11 pages at batch_size=500.

## Access Logs: access_logs.csv

- **Location inside container:** `/app/output/access_logs.csv`
- **Written by:** `_write_access_log()` in `main.py` — called after every authenticated request
- **Extract with:** `bash repo/scripts/extract-logs.sh`

### Schema

| Column | Description |
|---|---|
| `timestamp_utc` | ISO-8601 UTC timestamp of the request |
| `team_name` | Team display name from api_keys.json |
| `api_key_prefix` | First 8 chars of the token (safe to log) |
| `endpoint` | `/info`, `/logs/current` |
| `http_method` | `GET` |
| `page` | Page number (empty for /info) |
| `http_status_code` | 200, 429, 503 |
| `records_returned` | Rows in response (empty for /info) |
| `window_start` | Window start ISO-8601 |
| `window_end` | Window end ISO-8601 |
| `latency_ms` | Server-side processing time in milliseconds |

### Example row

```
2026-03-24T01:33:12+00:00,TestTeam,santiadm,/logs/current,GET,1,200,500,2026-03-24T01:30:00+00:00,2026-03-24T02:00:00+00:00,14.3
```

## Generating new data

```bash
cd repo
python generate_synthetic_data.py
# Output: output/logs.csv
```

Then copy into the volume:
```bash
podman run --rm \
  -v soc_api_output:/data \
  -v $(pwd)/output/logs.csv:/src/logs.csv:ro \
  alpine cp /src/logs.csv /data/logs.csv

podman restart soc_api
podman restart tunnel