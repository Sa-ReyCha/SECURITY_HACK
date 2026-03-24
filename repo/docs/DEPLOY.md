# Deploy — SAP SOC Log Ingestion API

Guía completa para levantar la API en Docker y exponerla a internet vía Cloudflare Tunnel.

---

## Prerequisitos

| Herramienta | Versión mínima | Instalación |
|---|---|---|
| Docker Desktop | 24+ | https://www.docker.com/products/docker-desktop |
| Cuenta Cloudflare | (gratis) | https://dash.cloudflare.com/sign-up |
| Dominio en Cloudflare | cualquiera | o usa el subdominio `.trycloudflare.com` (sin cuenta) |

---

## Paso 1 — Generar el CSV de datos

Si aún no existe `output/logs.csv`:

```bash
# desde la raíz del proyecto
python generate_synthetic_data.py
```

---

## Paso 2 — Configurar el token de Cloudflare Tunnel

### Opción A — Tunnel con tu propio dominio (recomendado para hackathon)

1. Ve a **Cloudflare Dashboard → Zero Trust → Networks → Tunnels**
2. Crea un nuevo tunnel → elige **Docker**
3. Cloudflare te dará un comando como:
   ```
   cloudflared tunnel run --token eyJhGc...
   ```
4. Copia **solo el token** (la parte después de `--token`).
5. Crea un archivo `.env` en la **raíz del proyecto** (junto a `docker-compose.yml`):

```bash
# .env  (raíz del proyecto — NO el de fast_app/)
TUNNEL_TOKEN=eyJhGc...tu_token_aqui...
```

6. En el dashboard de Cloudflare, configura el **Public Hostname** del tunnel:
   - Subdomain: `soc-api`  (o el que quieras)
   - Domain: `tudominio.com`
   - Service: `http://api:8000`   ← nombre del servicio Docker, no localhost

### Opción B — Tunnel temporal sin cuenta (solo para pruebas rápidas)

```bash
# Levanta solo la app primero
docker compose up api --build -d

# Luego crea un tunnel temporal (genera URL *.trycloudflare.com)
docker run --rm cloudflare/cloudflared:latest tunnel --no-autoupdate \
  --url http://host.docker.internal:8000

# La URL aparece en stdout: https://xxxx-yyyy.trycloudflare.com
```

> ⚠️ La URL cambia cada vez que reinicias. Úsala solo para demos rápidas.

---

## Paso 3 — Levantar todo

```bash
# Desde la raíz del proyecto (donde está docker-compose.yml)
docker compose up --build
```

Verás:
```
soc_api     | INFO:     Application startup complete.
soc_tunnel  | Registered tunnel connection ...
soc_tunnel  | Connection ... registered with protocol: quic
```

Verifica que funciona:
```bash
# Local
curl http://localhost:8000/health

# Remoto (reemplaza con tu URL)
curl https://soc-api.tudominio.com/health
```

Ambos deben responder: `{"status":"ok"}`

---

## Paso 4 — Distribuir tokens a los equipos

Edita `fast_app/api_keys.json` (se monta como volumen, no requiere rebuild):

```json
{
  "team-alpha-secret-token-abc123": "Team Alpha",
  "team-bravo-secret-token-def456": "Team Bravo",
  "team-charlie-secret-token-ghi789": "Team Charlie"
}
```

Reinicia solo el servicio api para que tome los nuevos tokens:

```bash
docker compose restart api
```

Cada equipo usa:
```
Authorization: Bearer team-alpha-secret-token-abc123
```

---

## Paso 5 — Monitoreo

### Ver logs en tiempo real
```bash
docker compose logs -f api
```

### Inspeccionar el access log (quién pidió qué y cuándo)
```bash
# Últimas 20 requests
tail -20 output/access_logs.csv

# Requests bloqueadas (429)
grep ",429," output/access_logs.csv

# Requests por equipo
awk -F',' 'NR>1 {print $2}' output/access_logs.csv | sort | uniq -c | sort -rn
```

---

## Comandos útiles

```bash
# Levantar en background
docker compose up --build -d

# Apagar todo
docker compose down

# Rebuild solo la app (sin reiniciar tunnel)
docker compose up --build api -d

# Ver estado
docker compose ps

# Entrar al contenedor para debug
docker exec -it soc_api bash
```

---

## Estructura de archivos

```
SEC_HACK/
├── docker-compose.yml        ← orquestación
├── .env                      ← TUNNEL_TOKEN (NO subir a git)
├── output/
│   ├── logs.csv              ← datos generados (montado en contenedor)
│   └── access_logs.csv       ← escrito por la app en runtime
├── fast_app/
│   ├── Dockerfile
│   ├── .env                  ← config de la app (BATCH_SIZE, etc.)
│   ├── api_keys.json         ← tokens de los equipos
│   └── main.py
└── generate_synthetic_data.py
```

---

## Variables de configuración (`fast_app/.env`)

| Variable | Default | Descripción |
|---|---|---|
| `BATCH_SIZE` | `500` | Rows por página |
| `MAX_REQUESTS_PER_WINDOW` | `220` | Requests permitidas por ventana de 30 min |
| `BLOCK_DURATION_MINUTES` | `10` | Minutos de bloqueo al superar el límite |
| `API_KEYS_PATH` | `api_keys.json` | Path al JSON de tokens |
| `ACCESS_LOG_PATH` | `../output/access_logs.csv` | Dónde escribir el access log |
| `CSV_PATH` | `../output/logs.csv` | Datos de entrada |