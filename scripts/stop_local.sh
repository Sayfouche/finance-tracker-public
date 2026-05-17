#!/bin/bash
set -euo pipefail

MODE="${1:-all}"

ports_for_mode() {
  case "$1" in
    dev)
      echo "8000 3000"
      ;;
    local-prod)
      echo "8100 3100"
      ;;
    all)
      echo "8000 3000 8100 3100"
      ;;
    *)
      echo "Usage: scripts/stop_local.sh dev|local-prod|all" >&2
      exit 1
      ;;
  esac
}

for port in $(ports_for_mode "$MODE"); do
  pids="$(lsof -ti ":$port" 2>/dev/null || true)"
  if [ -z "$pids" ]; then
    echo "Port $port: aucun process"
    continue
  fi

  echo "Port $port: arret $pids"
  kill $pids 2>/dev/null || true
done
