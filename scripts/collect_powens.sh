#!/bin/bash
# Collecte Powens — fenêtre glissante 30 jours.
# Lancé par launchd ou manuellement : ./scripts/collect_powens.sh
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_DIR="$PROJECT/agents/account_collector"
ENV_FILE="$AGENT_DIR/.env"
CONFIG="$AGENT_DIR/config/accounts.powens.json"
SNAPSHOTS_DIR="$AGENT_DIR/snapshots"
LOG_DIR="$PROJECT/runtime/local-prod/logs"
LOG_FILE="$LOG_DIR/collect_powens.log"
PYTHON="$PROJECT/.venv/bin/python"

DATE_TO="$(date +%Y-%m-%d)"
DATE_FROM="$(date -v-30d +%Y-%m-%d 2>/dev/null || date -d '30 days ago' +%Y-%m-%d)"
SNAPSHOT_NAME="$(date +%Y%m%d_%H%M%S)_powens.json"
OUTPUT="$SNAPSHOTS_DIR/$SNAPSHOT_NAME"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

mkdir -p "$SNAPSHOTS_DIR" "$LOG_DIR"

log "--- collect_powens démarré ---"
log "Fenêtre : $DATE_FROM → $DATE_TO"
log "Snapshot : $OUTPUT"

if [ ! -f "$ENV_FILE" ]; then
  log "ERREUR : $ENV_FILE introuvable. Configure le .env avant de lancer le scheduler."
  exit 1
fi

if [ ! -f "$CONFIG" ]; then
  log "ERREUR : $CONFIG introuvable."
  exit 1
fi

cd "$AGENT_DIR"
"$PYTHON" -m account_collector \
  --env-file "$ENV_FILE" \
  collect \
  --provider powens \
  --config "$CONFIG" \
  --date-from "$DATE_FROM" \
  --date-to "$DATE_TO" \
  --output "$OUTPUT" \
  2>&1 | tee -a "$LOG_FILE"

log "Snapshot écrit : $OUTPUT"
log "--- collect_powens terminé ---"
