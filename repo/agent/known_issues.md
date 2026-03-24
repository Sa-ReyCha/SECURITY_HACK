# Known Issues & Fixes

All issues below were discovered and resolved during the session on 2026-03-23/24.

---

## 1. Container logs showed no HTTP requests

**Symptom:** `podman logs soc_api` only showed startup messages, no request lines.

**Root cause:** Two problems:
1. Uvicorn was started with `--no-access-log` flag → suppressed all HTTP logs
2. The app wrote requests only to `access_logs.csv` (file), not stdout

**Fix:**
- Removed `--no-access-log` from `fast_app/Dockerfile` CMD
- Added `print(f"[access] ...", flush=True)` inside `_write_access_log()` in `main.py`

**Lesson:** `logger.info()` fails silently under uvicorn — the `main` module logger is not configured at INFO level. Always use `print(..., flush=True)` for stdout output in this app.

---

## 2. Healthcheck: `SyntaxError: invalid syntax` on `import`

**Symptom:** Container showed `(unhealthy)`. Healthcheck output: `SyntaxError: invalid syntax` at `import`.

**Root cause:** Multi-line YAML flow sequence in `podman-compose.yml`:
```yaml
test: ["CMD", "python3", "-c",
       "import http.client; ..."]
```
The YAML parser split the `-c` argument at the newline — Python received only `import` as the code string, not the full expression.

**Fix:** Use `CMD-SHELL` with a single-line string:
```yaml
test: ["CMD-SHELL", "python3 -c \"import http.client; c=http.client.HTTPConnection('127.0.0.1',8000,timeout=4); c.request('GET','/health'); r=c.getresponse(); exit(0 if r.status==200 else 1)\""]
```

**Lesson:** Never split a `CMD` array across lines in YAML when one element is a code string. Use `CMD-SHELL` + a single-line string instead.

---

## 3. Healthcheck: `HTTP Error 307: Temporary Redirect`

**Symptom:** Container showed `(unhealthy)`. Healthcheck output: `urllib.error.HTTPError: HTTP Error 307`.

**Root cause:** The original healthcheck used `urllib.request.urlopen()` which does not follow HTTP 307 redirects. FastAPI returns 307 for some redirect scenarios.

**Fix:** Replaced `urllib.request` with `http.client.HTTPConnection` which connects directly without following redirects:
```python
import http.client
c = http.client.HTTPConnection('127.0.0.1', 8000, timeout=4)
c.request('GET', '/health')
r = c.getresponse()
exit(0 if r.status == 200 else 1)
```

Also increased `start_period` from 10s → 60s to give the container time to load the 1.2M-row CSV before healthcheck failures count.

---

## 4. Public URL returns 503 after container rebuild

**Symptom:** `https://soc-api.840127.xyz` returns HTTP 503 after running `podman compose up --build`.

**Root cause:** When `soc_api` is recreated, it gets a new internal IP address. The `tunnel` container caches the old IP and can no longer reach the backend.

**Fix:** Always restart the tunnel after rebuilding the API container:
```bash
cd repo
podman compose -f podman-compose.yml up --build -d
podman restart tunnel
```

**Lesson:** This is a Podman/Docker DNS caching issue. The tunnel resolves `api:8000` at startup and doesn't re-resolve when the container IP changes.

---

## 5. Transient 503 during startup

**Symptom:** First request after container start returns HTTP 503.

**Root cause:** The app returns 503 from `/logs/current` while `_df is None` (i.e., while `logs.csv` is still loading). Loading 1.2M rows takes ~10-15 seconds.

**Behavior:** This is expected and by design. The `/health` endpoint always returns 200 regardless of data load state.

**Mitigation:** `start_period: 60s` in the healthcheck gives the container time to load before failures count. Teams should retry after ~15 seconds if they hit 503 at startup.

---

## 6. `NameError: name 'logger' is not defined`

**Symptom:** App crashed with `NameError: name 'logger' is not defined` in `_write_access_log`.

**Root cause:** A `replace_in_file` operation added a `logger.info()` call but the `import logging` and `logger = logging.getLogger(__name__)` lines were missing from the file at that point.

**Fix:** Added to `main.py`:
```python
import logging
...
logger = logging.getLogger(__name__)
```

Then replaced `logger.info()` with `print(..., flush=True)` anyway (see issue #1).

---

## 7. `/config` endpoint exposed internal info

**Symptom:** Teams could call `/config` to see `csv_path` and `batch_size`.

**Decision:** Replaced `/config` with `/info` — a public-facing endpoint that returns useful pagination metadata (batch_size, window_start, window_end, total_records, total_pages) without exposing internal file paths.