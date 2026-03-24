# 📊 CSV Schema Reference

`output/logs.csv` has **44 columns**. Columns are either populated for
**System** rows, **LLM** rows, or **both**.

---

## Null pattern

| Column group | System rows | LLM rows |
|---|---|---|
| Shared columns (1–27 minus service/http/ip) | ✅ | ✅ |
| `service_id`, `http_status_code`, `client_ip` | ✅ | ❌ null |
| `llm_*` columns (28–44) | ❌ null | ✅ |
| `sap_llm_response_size`, `sap_llm_response_time` | ❌ null | ✅ |

---

## Full column reference

| # | Column | Type | Populated | Description |
|---|---|---|---|---|
| 1 | `_id` | string | Both | UUID v4 — unique per row |
| 2 | `_ignored` | string | Both | Empty metadata field (Elastic convention) |
| 3 | `_index` | string | Both | Elastic index name — `sap-logs-YYYY.MM` (System) or `llm-logs-YYYY.MM` (LLM) |
| 4 | `_score` | float | Both | Relevance score (0.5–1.0) |
| 5 | `@timestamp` | ISO 8601 UTC | Both | Event timestamp |
| 6 | `@version` | string | Both | Pipeline version — always `"1"` |
| 7 | `event_code_version` | string | Both | Semver code version (e.g. `2.3.1`) |
| 8 | `event_hash` | string | Both | SHA-256 of timestamp + app + source + row index |
| 9 | `@event_time_requested` | ISO 8601 UTC | Both | Original request timestamp |
| 10 | `headers_content_type` | string | Both | HTTP Content-Type (e.g. `application/json`) |
| 11 | `headers_http_host` | string | Both | HTTP Host header |
| 12 | `headers_http_request_method` | string | Both | HTTP verb (GET, POST, PUT, PATCH, DELETE) |
| 13 | `heathers_request_path` | string | Both | Request path — **note:** intentional typo `heathers` for schema compatibility |
| 14 | `sap_function_application` | string | Both | SAP application ID (e.g. `S4HANA`, `Ariba`) |
| 15 | `sap_source_type` | string | Both | Origin protocol (REST, RFC, ODATA, SOAP, …) |
| 16 | `sap_function_log_type` | string | Both | Log type (INFO, WARNING, ERROR, DEBUG, AUDIT, PERF, SECURITY, LLM_REQUEST, LLM_ERROR, LLM_TIMEOUT) |
| 17 | `sap_function_message` | string | Both | Human-readable event message |
| 18 | `sap_app_env` | string | Both | Environment (dev, qa, staging, prod, sandbox) |
| 19 | `sap_llm_response_size` | integer | LLM only | LLM response size in bytes |
| 20 | `sap_llm_response_time` | integer | LLM only | LLM response time in ms |
| 21 | `region_id` | string | Both | Region ID (e.g. `EU-008`) |
| 22 | `region_name` | string | Both | Region display name (e.g. `Germany \| Frankfurt`) |
| 23 | `region_code` | string | Both | Short region code (e.g. `DE-FRA`) |
| 24 | `macro_region` | string | Both | Macro-region (North America, Europe, Asia, Middle East & Africa, South America, Australia) |
| 25 | `service_id` | string | System only | Internal service identifier |
| 26 | `http_status_code` | integer | System only | HTTP response code (200, 201, 400, 401, 403, 404, 500, …) |
| 27 | `client_ip` | string | System only | Client IPv4 address |
| 28 | `llm_model_id` | string | LLM only | Model identifier (e.g. `gpt-4o`, `claude-3-opus`) |
| 29 | `llm_provider` | string | LLM only | Model provider (OpenAI, Anthropic, Google, SAP, …) |
| 30 | `llm_prompt_id` | string | LLM only | Prompt template slug (e.g. `sales-summary`) |
| 31 | `llm_prompt_category` | string | LLM only | Prompt category (Analytics, Finance, SAP Joule, …) |
| 32 | `llm_prompt` | string | LLM only | Resolved prompt text (variables substituted) |
| 33 | `llm_prompt_tokens` | integer | LLM only | Token count of the prompt |
| 34 | `llm_completion_tokens` | integer | LLM only | Token count of the completion |
| 35 | `llm_total_tokens` | integer | LLM only | `llm_prompt_tokens + llm_completion_tokens` |
| 36 | `llm_response_time_ms` | integer | LLM only | End-to-end response time in ms |
| 37 | `llm_response_size_bytes` | integer | LLM only | Response payload size in bytes |
| 38 | `llm_status` | string | LLM only | `success`, `error`, or `timeout` |
| 39 | `llm_error_message` | string | LLM only | Error message if `llm_status != success`, else null |
| 40 | `llm_cost_usd` | float | LLM only | Estimated cost: `cost_per_1k_tokens × total_tokens / 1000` |
| 41 | `llm_temperature` | float | LLM only | Model temperature (0.0–1.5) |
| 42 | `llm_top_p` | float | LLM only | Top-p sampling parameter (0.5–1.0) |
| 43 | `llm_stream` | boolean | LLM only | Whether streaming was used (`True` / `False`) |
| 44 | `llm_finish_reason` | string | LLM only | `stop`, `length`, `content_filter`, or `timeout` |

---

## Log type values

### System (`sap_function_log_type`)

| Value | Meaning |
|---|---|
| `INFO` | Normal operational event |
| `WARNING` | Degraded but non-critical condition |
| `ERROR` | Failure requiring attention |
| `DEBUG` | Verbose diagnostic trace |
| `AUDIT` | Security / compliance event |
| `PERF` | Performance metric breach |
| `SECURITY` | Security observation (low-severity) |

### LLM (`sap_function_log_type`)

| Value | Meaning |
|---|---|
| `LLM_REQUEST` | Successful inference call |
| `LLM_ERROR` | Failed inference call |
| `LLM_TIMEOUT` | Call exceeded timeout threshold (>28 s) |

---

## Notes

- `heathers_request_path` — the typo (`heathers` instead of `headers`) is
  **intentional** to preserve compatibility with the original Elastic schema.
- `event_hash` guarantees row uniqueness even if two rows share the same
  timestamp.
- `llm_cost_usd` is derived from `llm_models.json` — changing a model's
  `cost_per_1k_tokens` will affect costs on the next generation run.