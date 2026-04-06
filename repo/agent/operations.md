# Operations Guide

## Start everything (normal)

```bash
cd repo
podman compose -f podman-compose.yml up -d
```

## Rebuild API after code changes

```bash
cd repo
podman compose -f podman-compose.yml up --build -d
podman restart tunnel          # REQUIRED — tunnel caches old container IP
```

## Stop everything

```bash
cd repo
podman compose -f podman-compose.yml down
```

## Check container status

```bash
podman ps --format "{{.Names}}\t{{.Status}}"
# Expected:
# tunnel   Up X minutes
# soc_api  Up X minutes (healthy)
```

## View logs

```bash
podman logs -f soc_api    # API request logs (live)
podman logs -f tunnel     # Cloudflare tunnel status (live)
podman logs soc_api 2>&1 | grep "\[access\]"   # access log lines only
```

## Test endpoints locally

```bash
# Health (no auth)
curl http://localhost:8000/health

# Info
curl -H "Authorization: Bearer santiadmin99" http://localhost:8000/info

# Logs page 1
curl -H "Authorization: Bearer santiadmin99" "http://localhost:8000/logs/current?page=1"
```

## Test public URL

```bash
curl https://soc-api.840127.xyz/health
curl -H "Authorization: Bearer santiadmin99" https://soc-api.840127.xyz/info
```

## Extract access logs from volume

```bash
bash repo/scripts/extract-logs.sh
# Output: repo/output/access_logs.csv
```

## Add a new API key

1. Edit `repo/fast_app/api_keys.json`:
   ```json
   {
     "santiadmin99":        "TestTeam",
     "UPAEP_TEAM_KEY_2026": "UPAEP_TEAM",
     "NEW_TOKEN_HERE":      "NewTeamName"
   }
   ```
2. Restart the container (no rebuild needed — file is bind-mounted):
   ```bash
   podman restart soc_api
   podman restart tunnel
   ```

## Change batch size or rate limit

1. Edit `repo/fast_app/.env`:
   ```
   BATCH_SIZE=500
   MAX_REQUESTS_PER_WINDOW=200
   BLOCK_DURATION_MINUTES=10
   ```
2. Restart (no rebuild needed — `.env` is bind-mounted):
   ```bash
   podman restart soc_api
   podman restart tunnel
   ```

## Healthcheck

The container healthcheck runs every 30s after a 60s grace period:
```
python3 -c "import http.client; c=http.client.HTTPConnection('127.0.0.1',8000,timeout=4); c.request('GET','/health'); r=c.getresponse(); exit(0 if r.status==200 else 1)"
```

If the container shows `(unhealthy)`, check:
```bash
podman inspect soc_api --format '{{json .State.Health}}' | python3 -m json.tool | tail -20
```

## Diagnose 503 on public URL

**Step 1 — Identify where the 503 is coming from:**
```bash
curl -sv "https://soc-api.840127.xyz/health" 2>&1 | grep "< HTTP\|< server\|< cf-ray"
```
- `server: cloudflare` + empty body → tunnel/CF issue (go to step 2)
- `server: uvicorn` + JSON body → API issue (data still loading, wait 15s)

**Step 2 — Check local API:**
```bash
curl http://localhost:8000/health   # should be 200
```

**Step 3 — Check tunnel logs for errors:**
```bash
podman logs tunnel 2>&1 | grep -E "ERR|refused|failed" | grep -v "ping_group\|buffer"
```
- Errors present → `podman restart tunnel`
- No errors → Cloudflare propagation lag, wait 2–5 min then retry

**Step 4 — If still 503 after 5 min, restart tunnel:**
```bash
podman restart tunnel
until curl -sf https://soc-api.840127.xyz/health; do echo "waiting..."; sleep 10; done && echo "UP"
```

See `known_issues.md` Issue #8 for full diagnosis details.

## Auto-restart on boot

See `repo/docs/PODMAN_AUTO_RESTART.md` and `repo/scripts/start-on-boot.sh`.