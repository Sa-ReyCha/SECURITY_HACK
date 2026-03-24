# Estrategias para Recargar Datos sin Reiniciar Podman

## 🎯 Problema

La app carga datos una sola vez al iniciar. Cuando generas nuevos datos, necesitas reiniciar el contenedor para que los cargue.

## ✅ Soluciones

### Opción 1: Reinicio Automático con Cron (Recomendado para macOS)

Ejecuta un script que reinicie el contenedor periódicamente:

```bash
# Editar crontab
crontab -e

# Agregar esta línea para reiniciar cada hora
0 * * * * cd /Users/santireycha/Desktop/SEC_HACK && podman restart soc_api

# O cada 30 minutos
*/30 * * * * cd /Users/santireycha/Desktop/SEC_HACK && podman restart soc_api

# O cada 5 minutos
*/5 * * * * cd /Users/santireycha/Desktop/SEC_HACK && podman restart soc_api
```

**Ventajas:**
- ✅ Simple de implementar
- ✅ No requiere cambios en el código
- ✅ Funciona con cualquier versión

**Desventajas:**
- ❌ Downtime durante reinicio (~2-3 segundos)
- ❌ No es determinístico (reinicia aunque no haya datos nuevos)

---

### Opción 2: Reload en Caliente (Modificar la App)

Agregar un endpoint `/reload` que recargue los datos sin reiniciar:

#### Modificar `fast_app/main.py`:

Busca la sección de rutas y agrega esto:

```python
@app.post(
    "/reload",
    tags=["meta"],
    summary="Reload data from CSV without restarting",
    response_model={"status": str},
)
async def reload_data(
    team: TeamInfo = Depends(verify_token),
) -> dict[str, str]:
    """
    Force a reload of the logs CSV from disk.
    Only available to authenticated users.
    """
    global _df
    
    print(f"[reload] {team.team_name} triggered data reload")
    
    try:
        _df = pd.read_csv(
            settings.csv_path,
            dtype=str,
            keep_default_na=False,
        )
        _df["_ts"] = pd.to_datetime(_df["@timestamp"], utc=True, errors="coerce")
        
        await _write_access_log({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "team_name": team.team_name,
            "api_key_prefix": team.api_key_prefix,
            "endpoint": "/reload",
            "http_method": "POST",
            "page": "",
            "http_status_code": 200,
            "records_returned": len(_df),
            "window_start": "",
            "window_end": "",
            "latency_ms": "",
        })
        
        return {"status": f"✅ Reloaded {len(_df):,} rows"}
    except Exception as e:
        return {"status": f"❌ Error: {str(e)}"}
```

**Uso:**

```bash
# Generar datos
python generate_synthetic_data.py

# Recargar en la app (sin reiniciar)
curl -X POST -H "Authorization: Bearer dev-secret-token" \
  https://soc-api.840127.xyz/reload

# Verificar que funciona
curl -H "Authorization: Bearer dev-secret-token" \
  https://soc-api.840127.xyz/logs/current?page=1
```

**Ventajas:**
- ✅ Sin downtime
- ✅ Control manual o automático
- ✅ Instantáneo

**Desventajas:**
- ⚠️ Requiere modificar el código
- ⚠️ Puede causar race conditions si hay requests en paralelo

---

### Opción 3: Generar Datos Dentro del Contenedor

Agregar un servicio en `podman-compose.yml` que genere datos automáticamente:

```yaml
services:
  # ... (api y cloudflared)
  
  data-generator:
    build:
      context: .
      dockerfile: Dockerfile.datagen
    container_name: soc_datagen
    restart: no
    volumes:
      - ./output:/output
      - ./reference_data:/app/reference_data:ro
      - ./generate_synthetic_data.py:/app/generate_synthetic_data.py:ro
    environment:
      - PYTHONUNBUFFERED=1
    command: |
      sh -c "
        while true; do
          echo '[datagen] Generating synthetic data...'
          python generate_synthetic_data.py
          echo '[datagen] Generated. Sleeping 1 hour...'
          sleep 3600
        done
      "
```

Crear `Dockerfile.datagen`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install pandas pydantic
COPY generate_synthetic_data.py .
COPY reference_data ./reference_data
```

**Ventajas:**
- ✅ Completamente automatizado
- ✅ Genera datos cada hora (configurable)

**Desventajas:**
- ❌ Requiere Dockerfile adicional
- ❌ Más complejo de monitorear

---

### Opción 4: Script de Shell para Refresh Manual

Crear un script que:
1. Genere datos
2. Recargue el contenedor
3. Verifique que funciona

Crear `scripts/refresh-data.sh`:

```bash
#!/bin/bash
set -e

WORKDIR="/Users/santireycha/Desktop/SEC_HACK"
cd "$WORKDIR"

echo "[$(date)] Starting data refresh cycle..."

# 1. Generar datos
echo "[$(date)] Generating synthetic data..."
python generate_synthetic_data.py

# 2. Reiniciar contenedor
echo "[$(date)] Restarting Podman container..."
podman restart soc_api

# 3. Esperar a que esté listo
sleep 5

# 4. Verificar que funciona
echo "[$(date)] Verifying API..."
RESULT=$(curl -s -H "Authorization: Bearer dev-secret-token" \
  "https://soc-api.840127.xyz/logs/current?page=1" | jq '.total_records')

echo "[$(date)] API returned: $RESULT records"

if [ "$RESULT" -gt 0 ]; then
    echo "[$(date)] ✅ Success!"
else
    echo "[$(date)] ❌ Failed - no records found"
    exit 1
fi
```

**Uso:**

```bash
# Hacer ejecutable
chmod +x scripts/refresh-data.sh

# Ejecutar manualmente cuando necesites refrescar datos
./scripts/refresh-data.sh
```

---

## 📊 Comparación de Opciones

| Opción | Complejidad | Downtime | Automatización | Recomendación |
|--------|-------------|----------|-----------------|--------------|
| 1. Endpoint /reload | ⭐ Muy simple | Ninguno | Manual | 👍 Sin downtime |
| 2. Data generator | ⭐⭐ Mediano | Ninguno | ✅ Automática | Para producción |
| 3. Script manual | ⭐⭐ Mediano | 2-3s | Manual | 👍 Control total |

---

## 🚀 Recomendación Final

**Usar Opción 2: Endpoint /reload en Caliente**

Mejor solución porque:
- ✅ Sin downtime
- ✅ Control manual cuando lo necesites
- ✅ Instantáneo
- ✅ Perfecto para desarrollo y producción

---

## 🧪 Uso del Script Manual

```bash
# Generar datos nuevos y recargar contenedor
./scripts/refresh-data.sh
```

**Output esperado:**
```
[Thu Mar 19 01:23:03 CST 2026] Starting data refresh cycle...
[Thu Mar 19 01:23:03 CST 2026] Generating synthetic data...
...
[Thu Mar 19 01:23:13 CST 2026] ✅ Success!
```

El API ahora tendrá los datos nuevos sin reiniciar. ✅
