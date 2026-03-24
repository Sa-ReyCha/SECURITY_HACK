# 🗂️ Reference Data Guide

All lookup tables live in `reference_data/`. The generator reads them at
startup — **no Python changes needed** to extend any of them.

---

## File inventory

| File | Purpose | Key fields |
|---|---|---|
| `sap_applications.json` | SAP app IDs used in every log row | `id`, `name` |
| `sap_source_types.json` | Origin protocol / source type | `type` |
| `sap_log_types.json` | System log types + sampling weights | `type`, `weight` |
| `sap_errors.json` | SAP error codes for prompt variables | `code`, `description` |
| `sap_vendors.json` | Vendor names for prompt variables | `name` |
| `regions.json` | 100+ global regions | `id`, `name`, `code`, `macro_region` |
| `environments.json` | Deployment environments | `name` |
| `llm_models.json` | LLM models with cost metadata | `id`, `provider`, `cost_per_1k_tokens` |
| `llm_prompts.json` | Prompt templates with categories | `id`, `category`, `template` |
| `llm_error_messages.json` | LLM-specific error strings | `message` |
| `sys_messages.json` | System log message templates per type | keyed by log type |
| `services.json` | Internal service IDs | `id` |
| `http_methods.json` | HTTP verbs | `method` |
| `content_types.json` | MIME types | `type` |

---

## `sys_messages.json` — System log message templates

### Structure

```json
{
  "INFO":     ["template 1", "template 2", ...],
  "WARNING":  [...],
  "ERROR":    [...],
  "DEBUG":    [...],
  "AUDIT":    [...],
  "PERF":     [...],
  "SECURITY": [...]
}
```

### Available placeholders

| Placeholder | Resolved to |
|---|---|
| `{app}` | SAP application ID (e.g. `S4HANA`) |
| `{source}` | Source type (e.g. `REST`, `RFC`, `ODATA`) |
| `{tps}` | Random throughput (req/s) — PERF only |
| `{latency}` | Random latency (ms) — PERF only |
| `{cpu}` | Random CPU % — PERF only |
| `{gc}` | Random GC pause (ms) — PERF only |
| `{pool}` | Random connection pool % — PERF only |
| `{heap}` | Random heap (MB) — PERF only |
| `{deg}` | Random throughput degradation % — PERF only |
| `{iowait}` | Random I/O wait (ms) — PERF only |
| `{qdepth}` | Random queue depth — PERF only |

### How to add a new message

Append a string to the relevant list. Example — new INFO message:

```json
"INFO": [
  "..existing messages..",
  "SAP Joule copilot session closed for {app} after idle timeout via {source}."
]
```

> ⚠️ Only use placeholders listed in the table above. Unknown placeholders
> will appear literally in the output.

---

## `llm_prompts.json` — LLM prompt templates

### Structure

```json
[
  {
    "id":       "unique-slug",
    "category": "Category Name",
    "template": "Prompt text with {variable} placeholders."
  }
]
```

### Available placeholders

| Placeholder | Resolved to |
|---|---|
| `{region}` | Region name (e.g. `Germany \| Frankfurt`) |
| `{app}` | SAP application ID |
| `{vendor}` | Random vendor name |
| `{q}` | Quarter number (1–4) |
| `{error}` | Random SAP error code |

### Current categories

`Analytics`, `API Operations`, `Compliance`, `Finance`, `HR`,
`LLM Operations`, `Procurement`, `SAP Joule`, `Supply Chain`, `Support`

### How to add a new prompt

```json
{
  "id": "chatbot-billing-dispute",
  "category": "Customer Service",
  "template": "Draft a customer response for a billing dispute in {app} for region {region}."
}
```

Append the object to the array. The `id` must be unique (used as
`llm_prompt_id` in the CSV).

---

## `sap_log_types.json` — System log type weights

Controls how often each System log type appears. Weights are **relative**
(they do not need to sum to 100).

```json
[
  {"type": "INFO",     "weight": 40},
  {"type": "WARNING",  "weight": 20},
  {"type": "ERROR",    "weight": 15},
  {"type": "DEBUG",    "weight": 10},
  {"type": "AUDIT",    "weight": 10},
  {"type": "PERF",     "weight": 5},
  {"type": "SECURITY", "weight": 5}
]
```

**Example — simulate a high-error environment:**

```json
[
  {"type": "INFO",     "weight": 15},
  {"type": "WARNING",  "weight": 15},
  {"type": "ERROR",    "weight": 50},
  {"type": "DEBUG",    "weight": 5},
  {"type": "AUDIT",    "weight": 5},
  {"type": "PERF",     "weight": 5},
  {"type": "SECURITY", "weight": 5}
]
```

---

## `llm_models.json` — LLM model definitions

Each entry defines a model available for LLM log rows.

```json
{
  "id":                "gpt-4o",
  "provider":          "OpenAI",
  "cost_per_1k_tokens": 0.005
}
```

To add a new model (e.g. a SAP Joule model), append an entry with a unique
`id`. The cost field drives the `llm_cost_usd` column in the CSV.

---

## `regions.json` — Global regions

```json
{
  "id":           "EU-008",
  "name":         "Germany | Frankfurt",
  "code":         "DE-FRA",
  "macro_region": "Europe"
}
```

`macro_region` must be one of: `North America`, `Europe`, `Asia`,
`Middle East & Africa`, `South America`, `Australia`.

---

## `sap_applications.json` — SAP applications

```json
{"id": "S4HANA", "name": "SAP S/4HANA"}
```

The `id` value is what appears in the `sap_function_application` CSV column
and in `{app}` placeholders.

---

## Tips for agents

- All JSON files are loaded fresh each time `generate_synthetic_data.py` runs —
  no caching, no restart needed.
- Validate JSON syntax before saving (use `python3 -m json.tool <file>`).
- Keep `id` values URL-safe slugs (lowercase, hyphens) for prompt IDs.
- Do **not** rename or remove existing keys in `sys_messages.json` — the
  generator references them by exact key name.