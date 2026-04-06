# Agent Rebuild & Data Refresh Guide

Use this file when you need to update the data served by the API or rebuild the container after code changes.

---

## Quick reference

| Scenario | Steps |
|---|---|
| New date range / new logs.csv | [Data refresh](#1-data-refresh-new-logscsv) |
| Code change in `fast_app/` | [Code rebuild](#2-code-rebuild-fastapi-changes) |
| Add/remove API key | [API key update](#3-api-key-update-no-rebuild) |
| 503 after any restart | [503 fix](#4-503-after-restart) |

---

## 1. Data refresh (new logs.csv)

Use this when you have generated a new `output/logs.csv` (e.g. new date range, more rows) and want the API to serve the updated data. **No container rebuild needed.**

### Step 1 — Edit the date range (if needed)

Open `repo/generate_synthetic_data.py` and update:

```python
START_DATE = datetime(2026, 3, 30,  0, 0, 0, tzinfo=timezone.utc)
END_DATE   = datetime(2026, 4,  4,  0, 0, 0, tzinfo=timezone.utc)
```

Also adjust `N_ROWS` if you want more or fewer rows.

### Step 2 — Generate the new CSV

```bash
cd /Users/santi/Desktop/HACK/repo
python generate_synthetic_data.py
# Output: repo/output/logs.csv
# Takes ~30-60 seconds for 600k rows
```

Verify the output:
```bash
wc -l repo/output/logs.csv   # should be N_ROWS + 1 (header)
head -1 repo/output/logs.csv  # should show column names
```

### Step 3 — Copy CSV into the Podman volume

```bash
cd /Users/santi/Desktop/HACK/repo
podman run --rm \
  -v soc_api_output:/data \
  -v $(pwd)/output/logs.csv:/src/logs.csv:ro \
  alpine cp /src/logs.csv /data/logs.csv
```

Verify the copy:
```bash
podman run --rm -v soc_api_output:/data alpine wc -l /data/logs.csv
```

### Step 4 — Restart the API container

```bash
podman restart soc_api
```

The container will reload `logs.csv` from the volume on startup (~10-15 seconds).

### Step 5 — Restart the tunnel

```bash
podman restart tunnel
```

**Always restart the tunnel after restarting `soc_api`** — the tunnel caches the container IP and must re-resolve it.

### Step 6 — Verify

```bash
# Wait ~15s for CSV to load, then:
curl http://localhost:8000/health
# → {"status":"ok"}

curl -s -H "Authorization: Bearer santiadmin99" \
  "http://localhost:8000/info" | python3 -m json.tool
# → total_records should be > 0 if current time is within START_DATE–END_DATE

# Wait ~2 min for Cloudflare propagation, then:
until curl -sf https://soc-api.840127.xyz/health; do echo "waiting..."; sleep 10; done && echo "UP"
```

---

## 2. Code rebuild (FastAPI changes)

Use this when you have modified files in `repo/fast_app/` (e.g. `main.py`, `config.py`, `Dockerfile`, `requirements.txt`).

```bash
cd /Users/santi/Desktop/HACK/repo
podman compose -f podman-compose.yml up --build -d
podman restart tunnel   # REQUIRED — clears stale IP after rebuild
```

Then verify (same as Step 6 above).

> **Note:** Rebuilding recreates the `soc_api` container with a new IP. The tunnel MUST be restarted or it will keep hitting the old (dead) IP → 503.

---

## 3. API key update (no rebuild)

Edit `repo/fast_app/api_keys.json`:

```json
{
  "santiadmin99":        "TestTeam",
  "UPAEP_TEAM_KEY_2026": "UPAEP_TEAM",
  "NEW_TOKEN_HERE":      "NewTeamName"
}
```

Then restart (no rebuild — file is bind-mounted):

```bash
podman restart soc_api
podman restart tunnel
```

---

## 4. 503 after restart

If `https://soc-api.840127.xyz` returns 503 after any restart:

```bash
# 1. Check local API
curl http://localhost:8000/health
# → 200: API is fine, problem is tunnel/CF

# 2. Restart tunnel and wait for CF propagation (2-5 min)
podman restart tunnel
until curl -sf https://soc-api.840127.xyz/health; do echo "waiting..."; sleep 10; done && echo "UP"
```

See `known_issues.md` Issue #8 for full diagnosis.

---

## Important: date range and the API window

The API serves logs filtered to the **current 30-minute UTC window** (e.g. 14:00–14:30).
If the current time is outside `START_DATE`–`END_DATE`, `/info` will show `total_records: 0`.

**Always set `START_DATE`/`END_DATE` to cover the hackathon period.**

Check what window is active:
```bash
curl -s -H "Authorization: Bearer santiadmin99" \
  https://soc-api.840127.xyz/info | python3 -m json.tool
# window_start / window_end shows the active window
# total_records shows how many rows are in it
```

If `total_records` is 0, regenerate data with a date range that includes the current time.

---

## Full data refresh — one-liner

```bash
cd /Users/santi/Desktop/HACK/repo && \
python generate_synthetic_data.py && \
podman run --rm \
  -v soc_api_output:/data \
  -v $(pwd)/output/logs.csv:/src/logs.csv:ro \
  alpine cp /src/logs.csv /data/logs.csv && \
podman restart soc_api && \
sleep 5 && \
podman restart tunnel && \
echo "Waiting for CF propagation..." && \
until curl -sf https://soc-api.840127.xyz/health; do echo "waiting..."; sleep 10; done && \
echo "✅ API is UP"