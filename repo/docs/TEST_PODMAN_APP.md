# Pruebas de la App con Podman

## ✅ Estado Actual

La app está **corriendo correctamente** en Podman con Cloudflare Tunnel integrado.

### Contenedores activos

```
CONTAINER ID  IMAGE                                  COMMAND               STATUS
760c1f077702  docker.io/library/sec_hack-api:latest  uvicorn main:app ...  Up (healthy)
80cd7b06c9d7  docker.io/cloudflare/cloudflared:latest tunnel --no-autou...  Up
```

---

## 🧪 Endpoints Probados

### 1. Health Check ✅
```bash
curl -s http://localhost:8000/health
# Respuesta:
# {"status":"ok"}
```

### 2. Swagger UI ✅
```bash
curl -s http://localhost:8000/docs | head -20
# HTML de Swagger UI cargado correctamente
```

### 3. Authentication ✅
```bash
# Token inválido → 401
curl -s -H "Authorization: Bearer Development" http://localhost:8000/logs/current?page=1
# {"detail":"Invalid or missing Bearer token."}

# Token válido → 200
curl -s -H "Authorization: Bearer dev-secret-token" http://localhost:8000/logs/current?page=1
# {"request_time_utc":"2026-03-19T06:57:22.712545+00:00",...}
```

### 4. Logs Endpoint ✅
```bash
curl -s -H "Authorization: Bearer dev-secret-token" \
  'http://localhost:8000/logs/current?page=1' | jq '.'

# Respuesta:
{
  "request_time_utc": "2026-03-19T06:57:22.712545+00:00",
  "window_start": "2026-03-19T06:30:00+00:00",
  "window_end": "2026-03-19T07:00:00+00:00",
  "total_records": 0,
  "batch_size": 500,
  "current_page": 1,
  "total_pages": 1,
  "records_in_page": 0,
  "data": []
}
```

**Nota:** `total_records: 0` porque no hay logs en la ventana UTC actual.

---

## 🔑 Tokens Disponibles

Definidos en `fast_app/api_keys.json`:

| Token | Team |
|---|---|
| `dev-secret-token` | Development |
| `team-alpha-2026` | Team Alpha |
| `team-beta-2026` | Team Beta |
| `team-gamma-2026` | Team Gamma |
| `team-delta-2026` | Team Delta |
| `team-epsilon-2026` | Team Epsilon |

---

## 📊 Cloudflare Tunnel

- ✅ Servicio `cloudflared` corriendo
- ✅ Token cargado desde `.env`
- ✅ Conectado a `http://api:8000` internamente
- ✅ Expuesto a internet en tu Cloudflare Public Hostname

**Para verificar el tunnel:**

```bash
podman compose -f podman-compose.yml logs cloudflared | tail -20
```

---

## 🚀 Cómo Probar Localmente

### 1. Acceder a Swagger UI (interactive docs)
```
http://localhost:8000/docs
```
- Haz clic en "Authorize"
- Pega: `dev-secret-token`
- Haz clic en "Try it out" en cualquier endpoint

### 2. Test CLI completo
```bash
# Obtener logs de la ventana actual
curl -s -H "Authorization: Bearer dev-secret-token" \
  'http://localhost:8000/logs/current?page=1' | jq '.'

# Verificar config
curl -s -H "Authorization: Bearer dev-secret-token" \
  'http://localhost:8000/config' | jq '.'
```

### 3. Monitorear acceso
```bash
# Ver logs de acceso generados
tail -10 output/access_logs.csv

# Ver logs de la app
podman compose -f podman-compose.yml logs api
```

---

## 📝 Configuración Verificada

| Parámetro | Valor |
|---|---|
| Puerto local | 8000 |
| Batch size | 500 |
| API Keys | 6 tokens registrados |
| Access log | Escribiendo a `output/access_logs.csv` |
| CSV data | Cargando desde `output/logs.csv` |
| Cloudflare Tunnel | ✅ Conectado |

---

## ⚠️ Notas Importantes

1. **Ventana de datos UTC:** El API devuelve logs de la ventana UTC actual (30 minutos). La ventana calculada es:
   - 06:30 – 07:00 (si son las 06:57 UTC)
   - Los datos deben estar dentro de esa ventana para aparecer

2. **Rate limiting:** Por defecto permite 220 requests por ventana de 30 minutos por token

3. **Volúmenes en Podman Machine:** Los volúmenes en macOS están dentro de la VM de Podman, no en el host real

---

## 🛑 Para Detener

```bash
podman compose -f podman-compose.yml down
```

## ✨ Para Reiniciar

```bash
podman compose -f podman-compose.yml up --build