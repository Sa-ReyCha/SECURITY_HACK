# SAP / LLM Synthetic Log Generator

Genera un CSV unificado con logs sintéticos de **System** y **LLM** para pruebas, demos y desarrollo de dashboards.

---

## 📁 Estructura del proyecto

```
SEC_HACK/
├── generate_synthetic_data.py   # Script principal del generador
├── visualize_logs.ipynb         # Notebook de exploración y visualización
├── output/
│   └── logs.csv                 # CSV generado (3,000 filas × 44 columnas)
└── reference_data/
    ├── regions.json             # 100+ regiones globales con macro-región
    ├── environments.json        # dev, qa, staging, prod, sandbox
    ├── sap_applications.json    # Aplicaciones SAP (S/4HANA, Ariba, etc.)
    ├── sap_source_types.json    # Tipos de origen (REST, ODATA, RFC, etc.)
    ├── sap_log_types.json       # Tipos de log con pesos de distribución
    ├── llm_models.json          # Modelos LLM con costo por token
    ├── llm_prompts.json         # Plantillas de prompts con id y categoría
    ├── sys_messages.json        # Plantillas de mensajes por tipo de log System
    ├── services.json            # Servicios internos (auth, catalog, etc.)
    ├── http_methods.json        # GET, POST, PUT, PATCH, DELETE
    └── content_types.json       # application/json, text/xml, etc.
```

---

## 🚀 Cómo generar los datos

### Requisitos

- Python 3.8+
- No requiere librerías externas (usa solo stdlib: `csv`, `json`, `random`, `uuid`, `hashlib`)

### Ejecutar

```bash
python3 generate_synthetic_data.py
```

Salida esperada:
```
Generating 3,000 rows  (60% system / 40% LLM) …

✅  output/logs.csv
   Total rows :  3,000
   Columns    : 44

   Log type distribution:
     LLM_REQUEST         857  (system-only cols null)
     INFO                710  (LLM-only cols null)
     WARNING             390  (LLM-only cols null)
     ERROR               245  (LLM-only cols null)
     ...
```

---

## ⚙️ Configuración principal

Todas las opciones de alto nivel están al inicio de `generate_synthetic_data.py`:

```python
SEED       = 42           # Semilla para reproducibilidad
N_ROWS     = 3_000        # Total de filas a generar
PCT_SYSTEM = 0.60         # Proporción System vs LLM (0.60 = 60% system, 40% LLM)
START_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)
END_DATE   = datetime(2026, 3, 1, tzinfo=timezone.utc)
```

| Parámetro | Descripción | Valor por defecto |
|---|---|---|
| `N_ROWS` | Número total de filas | `3000` |
| `PCT_SYSTEM` | % de System logs (el resto son LLM) | `0.60` |
| `SEED` | Semilla aleatoria | `42` |
| `START_DATE` | Inicio del rango de fechas | `2025-01-01` |
| `END_DATE` | Fin del rango de fechas | `2026-03-01` |

---

## 📝 Configurar los prompts LLM → `reference_data/llm_prompts.json`

Cada entrada define un prompt reutilizable con variables:

| Campo | Descripción | Ejemplo |
|---|---|---|
| `id` | Identificador único (slug) | `"sales-summary"` |
| `category` | Categoría del caso de uso | `"Analytics"` |
| `template` | Texto del prompt con variables | `"Summarize the sales report for {region}."` |

**Variables disponibles en los templates:**

| Variable | Reemplazada con |
|---|---|
| `{region}` | Nombre de la región (e.g. `Germany \| Frankfurt`) |
| `{app}` | ID de la aplicación SAP (e.g. `S4HANA`) |
| `{vendor}` | Nombre de un vendor aleatorio |
| `{q}` | Número de trimestre (1–4) |
| `{error}` | Código de error SAP aleatorio |

**Ejemplo — agregar un nuevo prompt:**
```json
{
  "id": "chatbot-response",
  "category": "Customer Service",
  "template": "Draft a customer response for a billing dispute in {app} for region {region}."
}
```

**Categorías actuales:** Analytics, API Operations, Compliance, Finance, HR, LLM Operations, Procurement, SAP Joule, Supply Chain, Support

---

## 💬 Configurar mensajes de System logs → `reference_data/sys_messages.json`

El archivo es un objeto JSON donde cada clave es un tipo de log y el valor es una lista de plantillas:

```json
{
  "INFO":    ["Request to {app} completed successfully via {source}.", ...],
  "WARNING": ["High response time detected for {app} over {source}.", ...],
  "ERROR":   ["Connection timeout to {app} via {source}.", ...],
  "DEBUG":   [...],
  "AUDIT":   [...],
  "PERF":    [...]
}
```

**Variables disponibles en los templates:**

| Variable | Reemplazada con |
|---|---|
| `{app}` | ID de la aplicación SAP |
| `{source}` | Tipo de origen (REST, RFC, ODATA, …) |
| `{tps}` | Throughput aleatorio (req/s) |
| `{latency}` | Latencia aleatoria (ms) |
| `{cpu}` | Uso de CPU aleatorio (%) |
| `{gc}` | Pausa de GC aleatoria (ms) |
| `{pool}` | Saturación de connection pool (%) |
| `{heap}` | Uso de heap aleatorio (MB) |
| `{deg}` | Degradación de throughput (%) |
| `{iowait}` | Tiempo de I/O wait (ms) |
| `{qdepth}` | Profundidad de cola de requests |

**Ejemplo — agregar un nuevo mensaje de tipo ERROR:**
```json
"ERROR": [
  "Connection timeout to {app} via {source}.",
  "My custom error: {app} failed with unexpected state via {source}."
]
```

Para agregar mensajes basta con añadir entradas a la lista del tipo correspondiente en el JSON, sin tocar el script.

---

## 🎛️ Ajustar la distribución de log types

### System logs → `reference_data/sap_log_types.json`

Modifica el campo `weight` de cada tipo. Los pesos son **relativos** entre sí (no necesitan sumar 100):

```json
[
  {"type": "INFO",    "weight": 40},
  {"type": "WARNING", "weight": 20},
  {"type": "ERROR",   "weight": 15},
  {"type": "DEBUG",   "weight": 10},
  {"type": "AUDIT",   "weight": 10},
  {"type": "PERF",    "weight": 5}
]
```

**Ejemplo — simular un ambiente con muchos errores:**
```json
[
  {"type": "INFO",    "weight": 20},
  {"type": "WARNING", "weight": 15},
  {"type": "ERROR",   "weight": 50},
  {"type": "DEBUG",   "weight": 5},
  {"type": "AUDIT",   "weight": 5},
  {"type": "PERF",    "weight": 5}
]
```

### LLM logs → `generate_synthetic_data.py` (~línea 170)

```python
llm_log_type = random.choices(
    ["LLM_REQUEST", "LLM_ERROR", "LLM_TIMEOUT"],
    weights=[70, 20, 10]   # ← cambia aquí
)[0]
```

| Tipo | Descripción | Default |
|---|---|---|
| `LLM_REQUEST` | Llamada exitosa al LLM | 70% |
| `LLM_ERROR` | Error en la llamada | 20% |
| `LLM_TIMEOUT` | Timeout (>28s) | 10% |

---

## 📊 Esquema del CSV (`output/logs.csv`)

El CSV tiene **44 columnas**. Las columnas nulas siguen este patrón:

| Columna | System logs | LLM logs |
|---|---|---|
| `service_id`, `http_status_code`, `client_ip` | ✅ Poblada | ❌ Null |
| `llm_model_id` … `llm_finish_reason` | ❌ Null | ✅ Poblada |
| `sap_llm_response_size`, `sap_llm_response_time` | ❌ Null | ✅ Poblada |

### Columnas completas

| # | Columna | Descripción |
|---|---|---|
| 1 | `_id` | UUID único por fila |
| 2 | `_ignored` | Campo vacío (metadato Elastic) |
| 3 | `_index` | Índice Elastic (`sap-logs-YYYY.MM` / `llm-logs-YYYY.MM`) |
| 4 | `_score` | Score de relevancia (0.5–1.0) |
| 5 | `@timestamp` | Timestamp del evento (ISO 8601 UTC) |
| 6 | `@version` | Versión del pipeline (`"1"`) |
| 7 | `event_code_version` | Versión de código (e.g. `2.3.1`) |
| 8 | `event_hash` | SHA-256 del evento |
| 9 | `@event_time_requested` | Timestamp de la solicitud original |
| 10 | `headers_content_type` | Content-Type HTTP |
| 11 | `headers_http_host` | Host de la petición |
| 12 | `headers_http_request_method` | Método HTTP (GET, POST, …) |
| 13 | `heathers_request_path` | Path de la request (typo preservado) |
| 14 | `sap_function_application` | ID de la app SAP |
| 15 | `sap_source_type` | Tipo de origen (REST, RFC, ODATA, …) |
| 16 | `sap_function_log_type` | Tipo de log (INFO, ERROR, LLM_REQUEST, …) |
| 17 | `sap_function_message` | Mensaje legible del evento |
| 18 | `sap_app_env` | Ambiente (dev, qa, staging, prod, sandbox) |
| 19 | `sap_llm_response_size` | Tamaño de respuesta LLM (bytes) — solo LLM |
| 20 | `sap_llm_response_time` | Tiempo de respuesta LLM (ms) — solo LLM |
| 21 | `region_id` | ID de región (e.g. `EU-008`) |
| 22 | `region_name` | Nombre legible (e.g. `Germany \| Frankfurt`) |
| 23 | `region_code` | Código corto (e.g. `DE-FRA`) |
| 24 | `macro_region` | Macro-región (North America, Europe, Asia, …) |
| 25 | `service_id` | ID del servicio interno — solo System |
| 26 | `http_status_code` | Código HTTP (200, 404, 500, …) — solo System |
| 27 | `client_ip` | IP del cliente — solo System |
| 28 | `llm_model_id` | ID del modelo LLM — solo LLM |
| 29 | `llm_provider` | Proveedor (OpenAI, Anthropic, Google, …) — solo LLM |
| 30 | `llm_prompt_id` | ID de la plantilla de prompt (e.g. `sales-summary`) — solo LLM |
| 31 | `llm_prompt_category` | Categoría del prompt (Analytics, Finance, Support, …) — solo LLM |
| 32 | `llm_prompt` | Texto del prompt enviado (con variables resueltas) — solo LLM |
| 33 | `llm_prompt_tokens` | Tokens del prompt — solo LLM |
| 34 | `llm_completion_tokens` | Tokens de la respuesta — solo LLM |
| 35 | `llm_total_tokens` | Total de tokens — solo LLM |
| 36 | `llm_response_time_ms` | Tiempo de respuesta en ms — solo LLM |
| 37 | `llm_response_size_bytes` | Tamaño de respuesta en bytes — solo LLM |
| 38 | `llm_status` | Estado (`success`, `error`, `timeout`) — solo LLM |
| 39 | `llm_error_message` | Mensaje de error si aplica — solo LLM |
| 40 | `llm_cost_usd` | Costo estimado en USD — solo LLM |
| 41 | `llm_temperature` | Temperature del modelo (0.0–1.5) — solo LLM |
| 42 | `llm_top_p` | Top-p del modelo (0.5–1.0) — solo LLM |
| 43 | `llm_stream` | Si usó streaming (True/False) — solo LLM |
| 44 | `llm_finish_reason` | Razón de fin (`stop`, `length`, `content_filter`, `timeout`) — solo LLM |

---

## 🌍 Regiones disponibles

100+ regiones en 6 macro-regiones:

| Macro-región | Regiones incluidas |
|---|---|
| **North America** | Canada (5), Mexico (1), USA (28) |
| **Europe** | Austria, Belgium, Denmark, Finland, France, Germany, Hungary, Ireland, Italy, Netherlands, Norway, Poland, Spain, Sweden, Switzerland, Turkey, UK |
| **Asia** | China, India, Indonesia, Japan, Malaysia, Singapore, South Korea, Taiwan, Thailand |
| **Middle East & Africa** | Bahrain, Egypt, Israel, Qatar, Saudi Arabia, South Africa, UAE |
| **South America** | Brazil, Chile |
| **Australia** | New South Wales, Sydney, Victoria |

---

## 📈 Visualización

Abre `visualize_logs.ipynb` en Jupyter o VS Code y ejecuta todas las celdas:

```bash
jupyter notebook visualize_logs.ipynb
```

### Secciones del notebook

| # | Sección | Descripción |
|---|---|---|
| 1 | Load & Quick Overview | Carga el CSV, parsea timestamps, deriva columnas helper |
| 1b | Todas las columnas | Tabla con dtype, nulls, unique y ejemplo por columna |
| 2 | Null Pattern Heatmap | Tasa de nulos por columna (azul=System, naranja=LLM) |
| 3 | Log-Type Distribution | Conteo y pie System vs LLM |
| 4 | Time Series | Volumen mensual + heatmap hora × tipo |
| 5 | Region Breakdown | Macro-región y top 20 regiones |
| 6 | SAP Application | Logs por app y source type |
| 7 | Environment | Distribución por ambiente |
| 8 | System Deep-Dive | HTTP status codes, servicios, error rate |
| 9 | LLM Deep-Dive | Modelos, tokens, costo, finish reason |
| 10 | Response Times | Boxplots de latencia LLM y System |
| 11 | Timeline | Área apilada + MA7 + heatmap calendario + scatter |

---

## 🔄 Flujo de trabajo típico

```
1. Edita reference_data/*.json  →  ajusta pesos, agrega prompts/apps/regiones/modelos
2. Edita generate_synthetic_data.py  →  cambia N_ROWS, PCT_SYSTEM, fechas o pesos LLM
3. python3 generate_synthetic_data.py  →  genera output/logs.csv
4. Abre visualize_logs.ipynb  →  recarga df y explora los datos
```

---

## 📝 Notas

- El campo `heathers_request_path` tiene un typo intencional (`heathers` en lugar de `headers`) para preservar compatibilidad con el esquema original.
- Los timestamps se generan aleatoriamente en el rango `START_DATE`→`END_DATE`, uniformemente distribuidos.
- El `event_hash` es un SHA-256 del timestamp + app + source_type + índice de fila, garantizando unicidad.
- El costo LLM (`llm_cost_usd`) se calcula como `cost_per_1k_tokens × total_tokens / 1000` según el modelo.
- Los prompts se cargan de `reference_data/llm_prompts.json`. Las variables `{region}`, `{app}`, `{vendor}`, `{q}`, `{error}` se resuelven al generar cada fila. Para agregar nuevos prompts basta con añadir entradas al JSON sin tocar el script.