#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# extract-logs.sh
# Extracts access_logs.csv (and optionally logs.csv) from the soc_api
# Podman named volume to a local directory on the host.
#
# Usage:
#   ./scripts/extract-logs.sh                  # saves to ./output/
#   ./scripts/extract-logs.sh /tmp/my-logs     # saves to /tmp/my-logs/
#   ./scripts/extract-logs.sh ./output --all   # also extracts logs.csv
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

DEST="${1:-./output}"
ALL="${2:-}"
CONTAINER="soc_api"

mkdir -p "$DEST"

echo "📦 Extracting logs from container: $CONTAINER"
echo "📁 Destination: $DEST"
echo ""

# ── 1. Extract access_logs.csv ────────────────────────────────────────────────
if podman cp "${CONTAINER}:/app/output/access_logs.csv" "${DEST}/access_logs.csv" 2>/dev/null; then
    ROWS=$(wc -l < "${DEST}/access_logs.csv")
    echo "✅ access_logs.csv  →  ${DEST}/access_logs.csv  (${ROWS} lines)"
    echo ""
    echo "Last 5 entries:"
    tail -5 "${DEST}/access_logs.csv"
else
    echo "⚠️  access_logs.csv not found in container (no requests logged yet?)"
fi

echo ""

# ── 2. Optionally extract logs.csv ────────────────────────────────────────────
if [[ "$ALL" == "--all" ]]; then
    echo "Extracting logs.csv (this may take a moment — large file)..."
    if podman cp "${CONTAINER}:/app/output/logs.csv" "${DEST}/logs.csv" 2>/dev/null; then
        SIZE=$(du -sh "${DEST}/logs.csv" | cut -f1)
        echo "✅ logs.csv  →  ${DEST}/logs.csv  (${SIZE})"
    else
        echo "⚠️  logs.csv not found in container"
    fi
fi

echo ""
echo "Done. Files in ${DEST}:"
ls -lh "${DEST}/"