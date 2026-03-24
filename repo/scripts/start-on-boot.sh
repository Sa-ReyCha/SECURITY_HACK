#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# start-on-boot.sh
# Starts the Podman machine and then brings up the compose stack.
# Called by the LaunchAgent on macOS login.
# ─────────────────────────────────────────────────────────────────────────────

# LaunchAgents run with a minimal PATH; add Podman and Homebrew paths
export PATH="/opt/podman/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

COMPOSE_DIR="/Users/santireycha/Desktop/SEC_HACK"
COMPOSE_FILE="podman-compose.yml"
LOG_FILE="/tmp/sec_hack_boot.log"
MAX_WAIT=120   # seconds to wait for the Podman machine to become ready

echo "[$(date)] ── SEC_HACK boot script started ──" >> "$LOG_FILE"

# ── 1. Start the Podman machine (no-op if already running) ──────────────────
echo "[$(date)] Starting Podman machine..." >> "$LOG_FILE"
podman machine start >> "$LOG_FILE" 2>&1
# exit codes 0 (started) and 125 (already running) are both fine
MC=$?
if [ "$MC" -ne 0 ] && [ "$MC" -ne 125 ]; then
  echo "[$(date)] WARNING: podman machine start exited with code $MC (may be OK)" >> "$LOG_FILE"
fi

# ── 2. Wait until the Podman socket is responsive ───────────────────────────
elapsed=0
until podman info > /dev/null 2>&1; do
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    echo "[$(date)] ERROR: Podman not ready after ${MAX_WAIT}s. Aborting." >> "$LOG_FILE"
    exit 1
  fi
  echo "[$(date)] Waiting for Podman... (${elapsed}s elapsed)" >> "$LOG_FILE"
  sleep 5
  elapsed=$((elapsed + 5))
done

echo "[$(date)] Podman is ready." >> "$LOG_FILE"

# ── 3. Bring up the compose stack ───────────────────────────────────────────
cd "$COMPOSE_DIR" || { echo "[$(date)] ERROR: Cannot cd to $COMPOSE_DIR" >> "$LOG_FILE"; exit 1; }

echo "[$(date)] Running: podman compose -f $COMPOSE_FILE up -d" >> "$LOG_FILE"
podman compose -f "$COMPOSE_FILE" up -d >> "$LOG_FILE" 2>&1
STATUS=$?

if [ "$STATUS" -eq 0 ]; then
  echo "[$(date)] Stack started successfully." >> "$LOG_FILE"
else
  echo "[$(date)] ERROR: podman compose up -d failed (exit $STATUS)." >> "$LOG_FILE"
fi

echo "[$(date)] ── Boot script finished ──" >> "$LOG_FILE"
exit $STATUS