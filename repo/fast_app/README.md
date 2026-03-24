# SAP SOC Log Ingestion API

FastAPI application that serves SAP system and LLM interaction logs for the
SAP Security Operations Center (SOC) Hackathon.

---

## Quick start

```bash
# 1 – Install dependencies (from the fast_app/ directory)
cd fast_app
pip install -r requirements.txt

# 2 – (Optional) edit .env to change the token, batch size, or CSV path
#     Defaults already point to ../output/logs.csv

# 3 – Start the server
uvicorn main:app --reload --port 8000
```

Interactive docs are available at <http://localhost:8000/docs>.

---

## Configuration (server-side)

All settings live in `fast_app/.env`.  
**None of these are exposed as request parameters** – they are fixed by whoever
runs the server.

| Variable | Default | Description |
|---|---|---|
| `BATCH_SIZE` | `1000` | Rows returned per page |
| `BEARER_TOKEN` | `dev-secret-token` | Secret token clients must present |
| `CSV_PATH` | `../output/logs.csv` | Path to the CSV (relative to `fast_app/`) |

To change the batch size to 500, for example:

```
# fast_app/.env
BATCH_SIZE=500
```

Then restart the server – no code changes needed.

---

## Authentication

Every protected endpoint requires an `Authorization` header:

```
Authorization: Bearer dev-secret-token
```

---

## Endpoints

### `GET /health` — liveness probe (no auth)

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

### `GET /config` — show active server config (auth required)

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

### `GET /logs/current` — logs for the current 30-minute window (auth required)

Returns all rows from `logs.csv` whose `@timestamp` falls inside the current
UTC half-hour slot, delivered as a paginated batch.

**Half-hour window logic (UTC):**

| Current minute | Window returned |
|---|---|
| 00 – 29 | `HH:00 → HH:30` |
| 30 – 59 | `HH:30 → HH+1:00` |

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | integer ≥ 1 | `1` | Which page / batch to return |

**Example – first page:**

```bash
curl -H "Authorization: Bearer dev-secret-token" \
     "http://localhost:8000/logs/current?page=1"
```

**Example – third page:**

```bash
curl -H "Authorization: Bearer dev-secret-token" \
     "http://localhost:8000/logs/current?page=3"
```

**Response envelope:**

```json
{
  "window_start": "2026-03-18T12:00:00+00:00",
  "window_end":   "2026-03-18T12:30:00+00:00",
  "total_records": 54832,
  "batch_size": 1000,
  "current_page": 1,
  "total_pages": 55,
  "records_in_page": 1000,
  "data": [ { ... }, { ... } ]
}
```

---

## Notes

* The CSV is loaded **once at startup** into memory; no disk I/O on every
  request.
* The `_ts` helper column used for filtering is stripped from the response
  so clients never see it.
* If the current time falls outside the active data range, `total_records`
  will be `0` and `data` will be `[]` — this is expected behavior.
