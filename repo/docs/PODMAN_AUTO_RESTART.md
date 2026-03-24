# Reinicio Automático y Cron Jobs para Podman

## 🎯 Opciones Disponibles

### Opción 1: Reinicio Automático con Podman (Recomendado para desarrollo)

Edita `podman-compose.yml` para que el contenedor se reinicie automáticamente:

```yaml
services:
  api:
    build:
      context: ./fast_app
      dockerfile: Dockerfile
    container_name: soc_api
    restart: always  # ← Reinicia automáticamente si falla
    # ... resto de configuración
```

**Valores disponibles para `restart`:**
- `no` – No reinicia (default)
- `always` – Reinicia siempre, incluso después de apagar/prender
- `unless-stopped` – Reinicia a menos que se haya detenido explícitamente
- `on-failure` – Reinicia solo si el contenedor termina con error
- `on-failure:5` – Reinicia máximo 5 veces si falla

**Tu configuración actual:**
```yaml
restart: unless-stopped  # ✅ Ya está configurado!
```

---

### Opción 2: Reinicio Periódico con Cron Job (Host macOS)

Si necesitas reiniciar **cada X tiempo** (ej: cada hora):

**1. Crear script de reinicio:**

```bash
cat > ~/reinicio_podman.sh << 'EOF'
#!/bin/bash
# Reinicia el contenedor soc_api cada hora

CONTAINER_NAME="soc_api"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

if podman ps | grep -q $CONTAINER_NAME; then
    echo "[$TIMESTAMP] Restarting $CONTAINER_NAME..."
    podman restart $CONTAINER_NAME
    echo "[$TIMESTAMP] ✅ Restart complete"
else
    echo "[$TIMESTAMP] ❌ Container $CONTAINER_NAME not found"
fi
EOF

chmod +x ~/reinicio_podman.sh
```

**2. Configurar Cron Job (macOS):**

```bash
# Abre el editor de crontab
crontab -e

# Agrega esta línea (reinicia cada hora a las :00)
0 * * * * ~/reinicio_podman.sh >> ~/podman_restart.log 2>&1

# O cada 30 minutos
*/30 * * * * ~/reinicio_podman.sh >> ~/podman_restart.log 2>&1
```

**3. Verificar que funciona:**

```bash
# Ver cron jobs activos
crontab -l

# Ver logs
tail -f ~/podman_restart.log
```

---

### Opción 3: Reinicio con Timer de Systemd (Linux)

**Solo si usas Podman en Linux** (no aplica en macOS):

```bash
# Crear archivo de servicio
sudo tee /etc/systemd/system/podman-restart-soc-api.timer << EOF
[Unit]
Description=Restart SOC API Container every hour
Requires=podman-restart-soc-api.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=1h
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

# Crear servicio asociado
sudo tee /etc/systemd/system/podman-restart-soc-api.service << EOF
[Unit]
Description=Restart SOC API Podman Container
After=podman.service

[Service]
Type=oneshot
ExecStart=/usr/bin/podman restart soc_api

[Install]
WantedBy=multi-user.target
EOF

# Habilitar y activar
sudo systemctl daemon-reload
sudo systemctl enable podman-restart-soc-api.timer
sudo systemctl start podman-restart-soc-api.timer

# Ver estado
sudo systemctl status podman-restart-soc-api.timer
```

---

