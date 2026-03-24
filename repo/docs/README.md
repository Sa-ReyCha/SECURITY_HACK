# 📚 Documentation Index

This folder contains all project documentation for the
**SAP / LLM Synthetic Log Generator**.

---

## Agent / instruction guides

| File | What it covers |
|---|---|
| [project-overview.md](./project-overview.md) | High-level architecture, goals, and component map |
| [data-generation.md](./data-generation.md) | How to run and configure the synthetic data generator |
| [reference-data.md](./reference-data.md) | How to extend every `reference_data/*.json` file |
| [schema.md](./schema.md) | Full CSV column reference (44 columns, null patterns) |
| [api.md](./api.md) | FastAPI app — endpoints, auth, config, and examples |
| [deployment.md](./deployment.md) | Docker / Podman deployment and auto-restart strategies |

---

## Original project documentation

| File | What it covers |
|---|---|
| [PROJECT_README.md](./PROJECT_README.md) | Main project README — full generator reference (Spanish) |
| [DEPLOY.md](./DEPLOY.md) | Step-by-step remote server deployment |
| [PODMAN_SETUP.md](./PODMAN_SETUP.md) | First-time Podman installation and socket setup |
| [PODMAN_AUTO_RESTART.md](./PODMAN_AUTO_RESTART.md) | Systemd auto-restart for Podman containers |
| [RESTART_AND_RELOAD_STRATEGIES.md](./RESTART_AND_RELOAD_STRATEGIES.md) | Zero-downtime restart and data reload strategies |
| [TEST_PODMAN_APP.md](./TEST_PODMAN_APP.md) | Smoke-test suite for the deployed API |

---

## Quick orientation for agents

1. **Understand the project** → read `project-overview.md` first.
2. **Change what data is generated** → `reference-data.md` + `data-generation.md`.
3. **Work with the API** → `api.md`.
4. **Deploy or restart services** → `deployment.md`.
5. **Understand the output columns** → `schema.md`.