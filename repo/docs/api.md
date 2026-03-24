# 🌐 FastAPI — Log Ingestion API

The `fast_app/` directory contains a FastAPI server that exposes `output/logs.csv`
over HTTP for downstream consumers (dashboards, agents, SOC tools).

---

## Quick start

```bash
cd fast_app
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Interactive docs: <http://localhost:8000/docs>

---

## Configuration

All settings live in `fast_app/.env`. **None are exposed as request parameters.**

| Variable | Default | Description |
|---|---|---|
| `BATCH_SIZE` | `1000` | Rows returned per page |
| `BEARER_TOKEN` | `dev-secret-token` | Token clients must present |
| `CSV_PATH` | `../output/logs.csv` | Path to the CSV (relative to `fast_app/`) |

Example — change batch size to 500:

```ini
# fast_app/.env
BATCH_SIZE=500
```

Restart the server after editing `.env`.

---

## Authentication

All protected endpoints require:

```
Authorization: Bearer dev-secret-token
```

Replace `dev-secret-token` with the value of `BEARER_TOKEN` in `.env`.

---

## Endpoints

### `GET /health` — liveness probe *(no auth)*

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

### `GET /config` — active server config *(auth required)*

```bash
curl -H "Authorization: Bearer dev-secret-token" \
     http://localhost:8000/config
```

```json
{
  "batch_size": 1000,
  "csv_path": "../output/logs.csv"
}
```

---

### `GET /logs/current` — logs for the current 30-minute window *(auth required)*

Returns all rows whose `@timestamp` falls inside the current UTC half-hour slot,
delivered as a paginated batch.

**Half-hour window logic (UTC):**

| Current minute | Window returned |
|---|---|
| 00 – 29 | `HH:00 → HH:30` |
| 30 – 59 | `HH:30 → HH+1:00` |

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | integer ≥ 1 | `1` | Page / batch number |

**Examples:**

```bash
# First page
curl -H "Authorization: Bearer dev-secret-token" \
     "http://localhost:8000/logs/current?page=1"

# Third page
curl -H "Authorization: Bearer dev-secret-token" \
     "http://localhost:8000/logs/current?page=3"
```

**Response envelope:**

```json
{
  "window_start":    "2026-03-18T12:00:00+00:00",
  "window_end":      "2026-03-18T12:30:00+00:00",
  "total_records":   54832,
  "batch_size":      1000,
  "current_page":    1,
  "total_pages":     55,
  "records_in_page": 1000,
  "data": [ { ... }, { ... } ]
}
```

> If the current time falls outside the dataset's date range,
> `total_records` will be `0` and `data` will be `[]` — this is expected.

---

## API keys file

`fast_app/api_keys.json` stores named API keys for multi-consumer scenarios.
The server reads this file at startup. Format:

```json
{
  "consumer-name": "bearer-token-value"
}
```

---

## Implementation notes

- The CSV is loaded **once at startup** into memory — no disk I/O per request.
- The internal `_ts` helper column used for time-window filtering is stripped
  from all responses.
- The server is stateless — safe to run multiple replicas behind a load balancer.

---

## Running tests

```bash
cd fast_app
pytest tests/
```

Test output is written to `fast_app/tests/output/ingested_logs.csv`.

---

## Docker / Podman

See [deployment.md](./deployment.md) for container-based deployment.