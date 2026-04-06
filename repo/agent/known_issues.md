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

---

## 8. Public URL returns 503 — tunnel stale IP / Cloudflare propagation lag

**Observed:** 2026-03-27. Recurrent pattern after container restarts.

**Symptom:** `https://soc-api.840127.xyz/health` returns HTTP 503 with an **empty body**. Local `http://localhost:8000/health` returns 200. Tunnel logs show 4 registered Cloudflare connections with no errors.

**How to distinguish from other 503s:**

| Source | Body | `server` header |
|---|---|---|
| FastAPI (data loading) | `{"detail":"..."}` JSON | `uvicorn` |
| Cloudflare (tunnel issue) | **empty** | `cloudflare` |

Confirm with:
```bash
curl -sv "https://soc-api.840127.xyz/health" 2>&1 | grep "< HTTP\|< server\|< cf-ray"
# If you see "server: cloudflare" + empty body → tunnel issue, not API issue
```

**Root cause — two variants:**

**Variant A — Stale IP cache (most common after `compose up --build`):**
When `soc_api` is recreated it gets a new internal IP. The `tunnel` container resolved `api` at its own startup and cached that IP. After the API container is rebuilt, the tunnel still points to the old (now dead) IP → every proxied request fails → Cloudflare returns 503.

**Variant B — Cloudflare edge propagation lag (after any tunnel restart):**
After `podman restart tunnel`, cloudflared registers a new Connector ID with Cloudflare's edge. Cloudflare takes 2–5 minutes to propagate routing to the new connector. During that window, edge nodes return 503 even though the tunnel shows 4 registered connections.

**Diagnosis checklist:**
```bash
# 1. Is the API healthy locally?
curl http://localhost:8000/health
# → 200: API is fine, problem is tunnel/CF

# 2. Is DNS resolving correctly inside the stack?
podman exec soc_api python3 -c "import socket; print(socket.gethostbyname('api'))"
# → Should match: podman inspect soc_api --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'

# 3. Check tunnel logs for connection errors
podman logs tunnel 2>&1 | grep -E "ERR|refused|failed" | grep -v "ping_group\|buffer"
# → Clean (no errors): Variant B — wait 2-5 min
# → "connection refused": Variant A — restart tunnel immediately
```

**Fix:**
```bash
podman restart tunnel
# Wait ~2 minutes for Cloudflare propagation, then verify:
until curl -sf https://soc-api.840127.xyz/health; do echo "waiting..."; sleep 10; done && echo "UP"
```

**After `compose up --build`, always run:**
```bash
cd repo
podman compose -f podman-compose.yml up --build -d
podman restart tunnel   # REQUIRED — clears stale IP cache
```

**Lesson:** A 503 with empty body + `server: cloudflare` header always means the tunnel can't reach the backend OR Cloudflare hasn't propagated the new connector yet. The fix in both cases is `podman restart tunnel` + wait 2 min. Never waste time debugging the FastAPI app when you see an empty 503 body.
