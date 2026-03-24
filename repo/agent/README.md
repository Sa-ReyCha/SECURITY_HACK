# Agent Handoff — SAP SOC Log Ingestion API

This folder contains everything the next agent (or human) needs to understand, operate, and extend this project without prior context.

## Index

| File | Contents |
|---|---|
| `README.md` | This file — start here |
| `architecture.md` | System architecture, containers, volumes, tunnel |
| `api.md` | All API endpoints with request/response examples |
| `operations.md` | How to start, stop, rebuild, and debug |
| `config.md` | All configuration variables and files |
| `data.md` | Data structure, CSV schema, access logs |
| `known_issues.md` | Bugs found and fixed during this session |

## 30-second summary

- **What it is:** A FastAPI app that serves 1.2M SAP security log rows to hackathon teams via a paginated REST API.
- **How it runs:** Two Podman containers — `soc_api` (FastAPI) + `tunnel` (Cloudflare) — managed by `podman-compose.yml`.
- **Public URL:** `https://soc-api.840127.xyz`
- **Data:** Loaded from `output/logs.csv` at startup into a Pandas DataFrame (in-memory). Persisted in a named Podman volume `soc_api_output`.
- **Auth:** Bearer token per team, defined in `fast_app/api_keys.json`.
- **Access logs:** Every request is appended to `output/access_logs.csv` inside the container volume.