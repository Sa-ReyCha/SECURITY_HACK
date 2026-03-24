# Architecture

## Container Stack

```
Host (macOS, Podman)
│
├── soc_api  (container)
│   ├── Image:   localhost/repo-api:latest
│   ├── Build:   repo/fast_app/Dockerfile
│   ├── Port:    0.0.0.0:8000 → container:8000
│   ├── Restart: unless-stopped
│   └── Volumes:
│       ├── soc_api_output (named) → /app/output   [logs.csv + access_logs.csv]
│       ├── ./fast_app/api_keys.json → /app/api_keys.json  (read-only)
│       └── ./fast_app/.env         → /app/.env            (read-only)
│
└── tunnel  (container)
    ├── Image:   cloudflare/cloudflared:latest
    ├── Restart: unless-stopped
    ├── Command: tunnel --no-autoupdate run --url http://api:8000
    └── Env:     TUNNEL_TOKEN=<secret in .env>
```

## Network

Both containers share the default bridge network created by podman-compose.
The tunnel resolves `api` → `soc_api` container IP via Podman DNS.

**Critical:** When `soc_api` is recreated, it gets a new IP. The tunnel caches the old IP.
You MUST restart the tunnel after rebuilding the API container:

```bash
cd repo
podman compose -f podman-compose.yml up --build -d
podman restart tunnel
```

## Named Volume: soc_api_output

```
podman volume inspect soc_api_output
# Mountpoint: /Users/santi/.local/share/containers/storage/volumes/soc_api_output/_data
```

Contains:
- `logs.csv`         — 1,220,600 rows of SAP log data (read at startup)
- `access_logs.csv`  — written at runtime, one row per API request

To extract files from the volume:
```bash
bash repo/scripts/extract-logs.sh
# Copies access_logs.csv → repo/output/access_logs.csv
```

## Cloudflare Tunnel

- Public URL: `https://soc-api.840127.xyz`
- Tunnel ID: `aa516b9a-bfb1-414f-a03d-20e37ccdaf98`
- Connects to 4 Cloudflare edge nodes (Dallas dfw + Querétaro qro)
- Token stored in `repo/fast_app/.env` as `TUNNEL_TOKEN=...`

## Startup Sequence

1. `soc_api` starts → uvicorn binds on `:8000`
2. Lifespan loads `api_keys.json` → initialises `access_logs.csv` → loads `logs.csv` into Pandas (~10-15s for 1.2M rows)
3. During load, `/logs/current` returns HTTP 503 (data not ready)
4. After load, all endpoints respond normally
5. `tunnel` connects to Cloudflare and starts proxying to `http://api:8000`

The healthcheck has `start_period: 60s` to allow for the CSV load time.