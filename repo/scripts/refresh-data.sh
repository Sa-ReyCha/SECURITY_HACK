#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# refresh-data.sh
# Regenera logs.csv, lo copia al volumen del contenedor y reinicia la API.
#
# Uso:
#   cd /Users/santi/Desktop/HACK/repo
#   bash scripts/refresh-data.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

WORKDIR="/Users/santi/Desktop/HACK/repo"
cd "$WORKDIR"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║          SAP SOC API — Data Refresh Script           ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. Generar datos ──────────────────────────────────────────────────────────
echo "[$(date '+%H:%M:%S')] 📊 Generating synthetic data..."
python3 generate_synthetic_data.py
echo "[$(date '+%H:%M:%S')] ✅ logs.csv generated: $(du -sh output/logs.csv | cut -f1)"

# ── 2. Copiar al volumen del contenedor ───────────────────────────────────────
echo ""
echo "[$(date '+%H:%M:%S')] 📦 Copying logs.csv into container volume..."
podman cp output/logs.csv soc_api:/app/output/logs.csv
echo "[$(date '+%H:%M:%S')] ✅ Copy complete"

# ── 3. Reiniciar soc_api para recargar datos ──────────────────────────────────
echo ""
echo "[$(date '+%H:%M:%S')] 🔄 Restarting soc_api..."
podman restart soc_api
echo "[$(date '+%H:%M:%S')] ✅ soc_api restarted"

# ── 4. Esperar a que cargue el CSV (~15s para 1.6M filas) ─────────────────────
echo ""
echo "[$(date '+%H:%M:%S')] ⏳ Waiting 20s for CSV to load..."
sleep 20

# ── 5. Verificar health local ─────────────────────────────────────────────────
echo ""
echo "[$(date '+%H:%M:%S')] 🏥 Health check..."
HEALTH=$(curl -s http://localhost:8000/health)
echo "   Local: $HEALTH"

# ── 6. Verificar datos en ventana actual ──────────────────────────────────────
echo ""
echo "[$(date '+%H:%M:%S')] 📋 Checking current window data..."
INFO=$(curl -s -H "Authorization: Bearer santiadmin99" http://localhost:8000/info)
echo "   Info: $INFO"

RECORDS=$(echo "$INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_records',0))" 2>/dev/null || echo "0")
PAGES=$(echo "$INFO"   | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_pages',0))"   2>/dev/null || echo "0")
WINDOW=$(echo "$INFO"  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('window_start','?'))" 2>/dev/null || echo "?")

echo ""
echo "   Window : $WINDOW"
echo "   Records: $RECORDS"
echo "   Pages  : $PAGES"

# ── 7. Reiniciar tunnel ───────────────────────────────────────────────────────
echo ""
echo "[$(date '+%H:%M:%S')] 🌐 Restarting tunnel (clears stale IP cache)..."
podman restart tunnel
echo "[$(date '+%H:%M:%S')] ✅ Tunnel restarted — wait ~2 min for Cloudflare propagation"

# ── 8. Resultado final ────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
if [ "$RECORDS" -gt 0 ] 2>/dev/null; then
    echo "✅  SUCCESS — API serving $RECORDS records ($PAGES pages) for window $WINDOW"
else
    echo "⚠️   API is healthy but 0 records in current window."
    echo "    Check START_DATE/END_DATE in generate_synthetic_data.py"
    echo "    Current UTC time: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
fi
echo "══════════════════════════════════════════════════════"
echo ""