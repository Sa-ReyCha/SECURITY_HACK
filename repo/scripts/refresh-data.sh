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