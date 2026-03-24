# 🗺️ Project Overview

## Purpose

This project generates a **unified synthetic CSV dataset** containing two
interleaved log streams:

| Stream | Description |
|---|---|
| **System logs** | SAP application events (INFO, WARNING, ERROR, DEBUG, AUDIT, PERF, SECURITY) |
| **LLM logs** | AI/LLM inference calls (LLM_REQUEST, LLM_ERROR, LLM_TIMEOUT) including SAP Joule interactions |

The dataset is designed for **demos, dashboard development, SOC tooling tests,
and hackathon prototypes** — no real production data is used.

---

## Component Map

```
repo/
├── generate_synthetic_data.py   ← Main generator script (single entry point)
├── output/
│   └── logs.csv                 ← Generated dataset (44 columns, ~3 000 rows default)
├── reference_data/              ← JSON lookup tables consumed by the generator
│   ├── regions.json
│   ├── environments.json
│   ├── sap_applications.json
│   ├── sap_source_types.json
│   ├── sap_log_types.json       ← Controls System log type distribution (weights)
│   ├── sap_errors.json
│   ├── sap_vendors.json
│   ├── llm_models.json          ← LLM models with cost-per-token
│   ├── llm_prompts.json         ← Prompt templates with {variable} placeholders
│   ├── llm_error_messages.json
│   ├── sys_messages.json        ← System log message templates per log type
│   ├── services.json
│   ├── http_methods.json
│   └── content_types.json
├── fast_app/                    ← FastAPI server that serves logs.csv over HTTP
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env
├── docs/                        ← ← You are here — agent instruction files
├── visualize_logs.ipynb         ← Jupyter notebook for exploration
├── docker-compose.yml
└── podman-compose.yml
```

---

## Data Flow

```
reference_data/*.json
        │
        ▼
generate_synthetic_data.py  ──►  output/logs.csv
                                        │
                                        ▼
                                 fast_app/main.py  ──►  HTTP API  ──►  Consumers
                                                                   (dashboards, agents, SOC tools)
```

---

## Log Type Split

| Category | Default share | Log types |
|---|---|---|
| System | 60 % | INFO, WARNING, ERROR, DEBUG, AUDIT, PERF, SECURITY |
| LLM | 40 % | LLM_REQUEST, LLM_ERROR, LLM_TIMEOUT |

The split is controlled by `PCT_SYSTEM` in `generate_synthetic_data.py`.

---

## Key Design Decisions

- **No external dependencies** — the generator uses only Python stdlib
  (`csv`, `json`, `random`, `uuid`, `hashlib`).
- **Null pattern by design** — System-only columns are `null` in LLM rows and
  vice versa, mimicking a real heterogeneous log pipeline.
- **Reproducible** — a fixed `SEED = 42` produces the same dataset every run.
- **Extensible via JSON** — adding new apps, prompts, messages, or models
  never requires touching the Python script.
- **SAP Joule aware** — LLM prompt templates and INFO messages include
  SAP Joule-specific scenarios (copilot sessions, grounding, skill invocations).

---

## Agents — What You Can Safely Change

| Task | Where to change | Risk |
|---|---|---|
| Add/edit log message templates | `reference_data/sys_messages.json` | None — JSON only |
| Add/edit LLM prompt templates | `reference_data/llm_prompts.json` | None — JSON only |
| Add SAP applications or vendors | `reference_data/sap_applications.json`, `sap_vendors.json` | None |
| Adjust log type weights | `reference_data/sap_log_types.json` | None |
| Change row count or date range | `generate_synthetic_data.py` top constants | Low |
| Change LLM type weights | `generate_synthetic_data.py` ~line 170 | Low |
| Modify API behaviour | `fast_app/main.py` | Medium — test after |