# API Reference

Base URL (local):  `http://localhost:8000`
Base URL (public): `https://soc-api.840127.xyz`

All endpoints except `/health` require:
```
Authorization: Bearer <token>
```

---

## GET /health

No auth required. Used for liveness probes.

**Response 200:**
```json
{"status": "ok"}
```

---

## GET /info

Returns batch size and current-window pagination metadata.
Call this **before** your ingestion loop to know how many pages to fetch.

**Response 200:**
```json
{
  "batch_size": 500,
  "window_start": "2026-03-24T01:30:00+00:00",
  "window_end":   "2026-03-24T02:00:00+00:00",
  "total_records": 5119,
  "total_pages":   11
}
```

---

## GET /logs/current?page=N

Returns one page of log rows for the current UTC 30-minute window.

**Query params:**
- `page` (int, default=1) — 1-based page number

**Response 200:**
```json
{
  "request_time_utc": "2026-03-24T01:33:12.264180+00:00",
  "window_start":     "2026-03-24T01:30:00+00:00",
  "window_end":       "2026-03-24T02:00:00+00:00",
  "total_records":    5119,
  "batch_size":       500,
  "current_page":     1,
  "total_pages":      11,
  "records_in_page":  500,
  "data": [ { ...log row... }, ... ]
}
```

**Error responses:**
- `401` — invalid/missing token
- `422` — page out of range
- `429` — rate limit exceeded (see rate limiting below)
- `503` — data still loading at startup

### Window logic

| Server UTC minute | Window served |
|---|---|
| 00–29 | `HH:00:00 → HH:30:00` |
| 30–59 | `HH:30:00 → HH+1:00:00` |

### Recommended ingestion loop

```python
import requests

TOKEN   = "your-token"
BASE    = "https://soc-api.840127.xyz"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# 1. Get window info
info = requests.get(f"{BASE}/info", headers=HEADERS).json()
total_pages = info["total_pages"]

# 2. Fetch all pages
all_records = []
for page in range(1, total_pages + 1):
    r = requests.get(f"{BASE}/logs/current", headers=HEADERS, params={"page": page})
    all_records.extend(r.json()["data"])

import pandas as pd
df = pd.DataFrame(all_records)
```

---

## Rate Limiting

- **Limit:** 200 requests per 30-minute window per token (configurable via `MAX_REQUESTS_PER_WINDOW`)
- **Penalty:** 10-minute block when limit exceeded (configurable via `BLOCK_DURATION_MINUTES`)
- **Response:** HTTP 429 with `Retry-After` header and human-readable detail message
- **Disable:** Set `MAX_REQUESTS_PER_WINDOW=0` in `.env`

---

## API Keys

Defined in `fast_app/api_keys.json`:
```json
{
  "santiadmin99":        "TestTeam",
  "UPAEP_TEAM_KEY_2026": "UPAEP_TEAM"
}
```
Format: `{ "token": "team_name" }`.
Edit the file and restart the container to apply changes.

---

## Swagger UI

Available at: `https://soc-api.840127.xyz/docs`
ReDoc at:     `https://soc-api.840127.xyz/redoc`