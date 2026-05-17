#!/bin/bash
# Installe ou désinstalle le launchd pour la collecte Powens hebdomadaire.
# Usage : ./scripts/setup_scheduler.sh install
#         ./scripts/setup_scheduler.sh uninstall
#         ./scripts/setup_scheduler.sh status
#         ./scripts/setup_scheduler.sh run-now
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.finance-tracker.collect-powens"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/$LABEL.plist"
COLLECT_SCRIPT="$PROJECT/scripts/collect_powens.sh"
LOG_DIR="$PROJECT/runtime/local-prod/logs"

CMD="${1:-help}"

case "$CMD" in
  install)
    mkdir -p "$PLIST_DIR" "$LOG_DIR"
    chmod +x "$COLLECT_SCRIPT"

    cat > "$PLIST_FILE" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${COLLECT_SCRIPT}</string>
    </array>

    <!-- Dimanche à 3h00 -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/collect_powens.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/collect_powens_error.log</string>

    <!-- Ne pas relancer automatiquement si le script échoue -->
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST

    launchctl bootout "gui/$(id -u)" "$PLIST_FILE" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST_FILE"

    echo "Scheduler installé : $LABEL"
    echo "Plist : $PLIST_FILE"
    echo "Prochaine exécution : dimanche 03:00"
    echo "Logs : $LOG_DIR/collect_powens.log"
    ;;

  uninstall)
    if [ -f "$PLIST_FILE" ]; then
      launchctl bootout "gui/$(id -u)" "$PLIST_FILE" 2>/dev/null || true
      rm -f "$PLIST_FILE"
      echo "Scheduler désinstallé."
    else
      echo "Aucun scheduler installé."
    fi
    ;;

  status)
    if launchctl list | grep -q "$LABEL"; then
      echo "Scheduler actif : $LABEL"
      launchctl list "$LABEL" 2>/dev/null || true
    else
      echo "Scheduler non actif."
    fi
    if [ -f "$PLIST_FILE" ]; then
      echo "Plist présent : $PLIST_FILE"
    fi
    ;;

  run-now)
    echo "Lancement immédiat de la collecte..."
    bash "$COLLECT_SCRIPT"
    ;;

  *)
    echo "Usage : $0 {install|uninstall|status|run-now}"
    echo ""
    echo "  install    Installe le scheduler launchd (dimanche 03:00)"
    echo "  uninstall  Supprime le scheduler"
    echo "  status     Vérifie si le scheduler est actif"
    echo "  run-now    Lance la collecte immédiatement (pour tester)"
    exit 1
    ;;
esac
