# ⚙️ Data Generation Guide

## Quick start

```bash
cd repo
python3 generate_synthetic_data.py
```

Output: `output/logs.csv` — 44 columns, 3 000 rows by default.

---

## Top-level configuration

All knobs are constants at the top of `generate_synthetic_data.py`:

```python
SEED       = 42                                      # Reproducibility seed
N_ROWS     = 3_000                                   # Total rows to generate
PCT_SYSTEM = 0.60                                    # 60% System / 40% LLM
START_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)
END_DATE   = datetime(2026, 3, 1, tzinfo=timezone.utc)
```

| Constant | Effect |
|---|---|
| `SEED` | Change to get a different-but-reproducible dataset |
| `N_ROWS` | Scale up for load testing, scale down for quick iteration |
| `PCT_SYSTEM` | `0.0` = all LLM rows; `1.0` = all System rows |
| `START_DATE` / `END_DATE` | Timestamps are drawn uniformly from this range |

---

## System log type distribution

Controlled entirely by `reference_data/sap_log_types.json` — no script
changes needed. See [reference-data.md](./reference-data.md) for details.

---

## LLM log type distribution

Hardcoded weights inside `generate_synthetic_data.py` (~line 170):

```python
llm_log_type = random.choices(
    ["LLM_REQUEST", "LLM_ERROR", "LLM_TIMEOUT"],
    weights=[70, 20, 10]
)[0]
```

| Type | Default | Description |
|---|---|---|
| `LLM_REQUEST` | 70 % | Successful inference call |
| `LLM_ERROR` | 20 % | Failed inference call |
| `LLM_TIMEOUT` | 10 % | Timed-out call (response_time > 28 s) |

---

## Regenerating after reference data changes

Any edit to a `reference_data/*.json` file takes effect on the **next run**:

```bash
python3 generate_synthetic_data.py
```

No server restart or cache clear is needed.

---

## Expected console output

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

## Common recipes

### Generate a larger dataset for load testing

```python
N_ROWS = 50_000
```

### Simulate a high-error incident window

1. Edit `reference_data/sap_log_types.json` — raise `ERROR` weight to `50`.
2. Set `PCT_SYSTEM = 0.80` to get more System rows.
3. Run the generator.

### Narrow the date range to a single month

```python
START_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)
END_DATE   = datetime(2026, 2, 1, tzinfo=timezone.utc)
```

### Pin a different random seed

```python
SEED = 99
```

---

## Validating the output

```bash
# Row count
wc -l output/logs.csv

# Column count (should be 44)
head -1 output/logs.csv | tr ',' '\n' | wc -l

# Validate JSON reference files
for f in reference_data/*.json; do
  python3 -m json.tool "$f" > /dev/null && echo "OK: $f" || echo "FAIL: $f"
done