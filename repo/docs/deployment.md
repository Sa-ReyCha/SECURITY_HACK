# 🚀 Deployment Guide

The stack runs as two containers:

| Container | Role |
|---|---|
| `data-generator` | Runs `generate_synthetic_data.py` on a schedule to refresh `logs.csv` |
| `fast-app` | FastAPI server that serves the CSV over HTTP |

Both Docker Compose and Podman Compose configurations are provided.

---

## Prerequisites

- **Docker** (`docker compose`) **or** **Podman** (`podman-compose`)
- The `.env` file at `repo/.env` (copy from `.env.example` and fill in values)

---

## Docker Compose

```bash
cd repo

# Start both services in the background
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

Config file: `repo/docker-compose.yml`

---

## Podman Compose

```bash
cd repo

# Start
podman-compose up -d

# View logs
podman-compose logs -f

# Stop
podman-compose down
```

Config file: `repo/podman-compose.yml`

> See `PODMAN_SETUP.md` for first-time Podman installation and socket setup.

---

## Environment variables

All runtime config is read from `repo/.env`. Copy the example and edit:

```bash
cp repo/.env.example repo/.env
```

Key variables:

| Variable | Description |
|---|---|
| `BEARER_TOKEN` | API authentication token |
| `BATCH_SIZE` | Rows per API page |
| `CSV_PATH` | Path to the generated CSV |
| `N_ROWS` | Number of rows to generate |
| `PCT_SYSTEM` | System vs LLM log ratio |

---

## Auto-restart strategies

### Docker — always restart policy

```yaml
# docker-compose.yml
services:
  fast-app:
    restart: always
```

### Podman — systemd unit (recommended for rootless)

```bash
# Generate a systemd unit for the container
podman generate systemd --new --name fast-app > ~/.config/systemd/user/fast-app.service

# Enable and start
systemctl --user enable --now fast-app
```

Full instructions: `repo/PODMAN_AUTO_RESTART.md`

---

## Refreshing data without downtime

The `scripts/refresh-data.sh` script regenerates `logs.csv` and signals the
API container to reload — no restart required:

```bash
bash repo/scripts/refresh-data.sh
```

The API server detects the updated file and reloads it on the next request
cycle. See `RESTART_AND_RELOAD_STRATEGIES.md` for implementation details.

---

## Health check

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

Use this as the liveness probe in your orchestrator (Kubernetes, Nomad, etc.).

---

## Deploying to a remote server

See `repo/DEPLOY.md` for step-by-step instructions covering:

- SSH key setup
- Copying files to the server
- Starting the stack on boot via `scripts/start-on-boot.sh`
- Firewall / port configuration

---

## Testing the deployed app

See `repo/TEST_PODMAN_APP.md` for a curl-based smoke-test suite that validates
all endpoints against a running instance.