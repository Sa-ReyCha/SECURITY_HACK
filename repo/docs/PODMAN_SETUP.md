# Ejecutar la API en Podman

Guía para levantar la aplicación SAP SOC Log Ingestion API usando Podman en lugar de Docker.

## Prerequisitos

| Herramienta | Versión mínima | Instalación |
|---|---|---|
| Podman | 5.0+ | `brew install podman` |
| Podman Machine | - | Necesario en macOS: `podman machine init && podman machine start` |
| Cuenta Cloudflare | (gratis) | https://dash.cloudflare.com/sign-up (opcional) |

## Paso 0 — Iniciar Podman Machine (macOS/Windows)

En macOS, Podman requiere una máquina virtual. Inicialízala:

```bash
# Crear la máquina (solo primera vez)
podman machine init

# Iniciar la máquina
podman machine start

# Verificar que funciona
podman --version
podman ps
```

## Paso 1 — Generar datos de prueba

```bash
python generate_synthetic_data.py
```

Esto crea `output/logs.csv` con datos sintéticos de logs.

## Paso 2 — Opción A: Usar podman compose (recomendado)

Si tienes `podman-compose` instalado:

```bash
# Instalar podman-compose si no lo tienes
brew install podman-compose

# Levantar con podman-compose
podman-compose -f podman-compose.yml up --build
```

## Paso 2 — Opción B: Usar podman compose nativo (Podman 4.0+)

Sin `podman-compose`, usa el comando nativo de Podman:

```bash
podman compose -f podman-compose.yml up --build
```

## Paso 3 — Verificar que funciona

En otra terminal:

```bash
# Local
curl http://localhost:8000/health

# Debería responder:
# {"status":"ok"}
```

## Paso 4 — Configurar Cloudflare Tunnel (opcional)

Si quieres exponer la API a internet:

1. Ve a **Cloudflare Dashboard → Zero Trust → Networks → Tunnels**
2. Crea un nuevo tunnel
3. Selecciona **Docker** como opción (funciona igual con Podman)
4. Copia el token que te da Cloudflare
5. Crea `.env` en la raíz del proyecto:

```bash
TUNNEL_TOKEN=eyJhGc...tu_token_aqui...
```

6. Levanta nuevamente:

```bash
podman compose -f podman-compose.yml up --build
```

## Paso 5 — Comandos útiles

```bash
# Ver logs en tiempo real
podman compose -f podman-compose.yml logs -f api

# Detener servicios
podman compose -f podman-compose.yml down

# Rebuild solo la app
podman compose -f podman-compose.yml up --build api

# Ver estado de contenedores
podman ps

# Entrar a un contenedor para debug
podman exec -it soc_api bash

# Ver volúmenes
podman volume ls

# Limpiar todo (containers, imágenes, volúmenes)
podman system prune -a
```

## Diferencias entre Docker y Podman

| Aspecto | Docker | Podman |
|---|---|---|
| Arquitectura | Cliente-servidor con daemon | Sin daemon (rootless por defecto) |
| Máquina Virtual | No (en Linux) | Sí (en macOS/Windows via Podman Machine) |
| Ports | `localhost:8000` | `localhost:8000` (via Podman Machine) |
| Volúmenes | Igual sintaxis | Igual sintaxis |
| Compose | `docker-compose` | `podman-compose` o `podman compose` |

## Troubleshooting

### Error: "Cannot connect to Podman socket"

**Solución:** Inicia Podman Machine:

```bash
podman machine start
```

### Error: "Port 8000 already in use"

**Solución:** Detén los servicios previos o usa otro puerto:

```bash
# Edita podman-compose.yml:
ports:
  - "8001:8000"  # cambiar 8000 → 8001
```

### Error: "API health check failing"

**Solución:** Espera más tiempo o revisa los logs:

```bash
podman compose -f podman-compose.yml logs api
```

### Volúmenes no se sincronizando

**Nota:** En Podman Machine, los volúmenes están dentro de la VM. Usa:

```bash
# Copiar archivos a la VM
podman machine scp output/logs.csv /tmp/

# O montar con path absoluto (dentro de la máquina)
```

## Conectarse desde otra máquina

Si quieres acceder a la API desde otra máquina en la red:

```bash
# Obtén la IP de tu Mac
ipconfig getifaddr en0

# Luego accede desde otra máquina:
curl http://<TU_IP>:8000/health
```

Alternativamente, usa Cloudflare Tunnel para exponer a internet sin abrir puertos.