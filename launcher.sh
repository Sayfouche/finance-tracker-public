#!/bin/bash
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-dev}"
AGENT_DIR="$PROJECT/agents/account_collector"
DEV_RUNTIME="$PROJECT/runtime/dev"
PROD_RUNTIME="$PROJECT/runtime/local-prod"

port_in_use() {
  lsof -ti ":$1" > /dev/null 2>&1
}

run_terminal() {
  local title="$1"
  local command="$2"
  osascript -e "tell application \"Terminal\" to do script \"printf '\\\033]0;$title\\\007'; $command\""
}

ensure_demo_db() {
  local db_path="$DEV_RUNTIME/data/current/finance.demo.db"
  mkdir -p "$DEV_RUNTIME/data/current" "$DEV_RUNTIME/data/rollback" "$DEV_RUNTIME/logs"
  if [ ! -f "$db_path" ]; then
    echo "Initialisation DB demo mock: $db_path"
    (
      cd "$PROJECT/backend"
      DATABASE_URL="sqlite:///$db_path" ../.venv/bin/python -m scripts.seed_demo_data
    )
  fi
}

case "$MODE" in
  dev)
    BACKEND_PORT=8000
    FRONTEND_PORT=3000
    DB_PATH="$DEV_RUNTIME/data/current/finance.demo.db"
    BACKEND_DIR="$PROJECT/backend"
    FRONTEND_DIR="$PROJECT/frontend"
    NEXT_COMMAND="npm run dev -- --hostname 127.0.0.1 --port $FRONTEND_PORT"
    APP_ENV="demo"
    DATASET_LABEL="Compte demo - donnees mockees"
    ensure_demo_db
    ;;
  local-prod)
    BACKEND_PORT=8100
    FRONTEND_PORT=3100
    DB_PATH="$PROD_RUNTIME/data/current/finance.db"
    BACKEND_DIR="$PROD_RUNTIME/backend"
    FRONTEND_DIR="$PROD_RUNTIME/frontend"
    NEXT_BIN="$PROJECT/frontend/node_modules/.bin/next"
    NEXT_COMMAND="'$NEXT_BIN' start --hostname 127.0.0.1 --port $FRONTEND_PORT"
    APP_ENV="local-prod"
    DATASET_LABEL="Base locale prod"
    if [ ! -f "$DB_PATH" ] || [ ! -d "$FRONTEND_DIR/.next-local-prod" ] || [ ! -d "$BACKEND_DIR/api" ]; then
      echo "Runtime local-prod incomplet."
      echo "Lance d'abord: scripts/promote_local_prod.sh"
      exit 1
    fi
    ;;
  *)
    echo "Usage: ./launcher.sh dev|local-prod"
    exit 1
    ;;
esac

echo "Finance Tracker"
echo "Mode:        $MODE"
echo "Backend:     http://127.0.0.1:$BACKEND_PORT"
echo "Frontend:    http://127.0.0.1:$FRONTEND_PORT"
echo "DB:          $DB_PATH"
echo "Backend dir: $BACKEND_DIR"
echo "Frontend dir:$FRONTEND_DIR"
echo "Agent dir:   $AGENT_DIR"

if port_in_use "$BACKEND_PORT"; then
  echo "Backend deja en cours sur $BACKEND_PORT"
else
  echo "Demarrage backend..."
  run_terminal \
    "finance-$MODE-backend" \
    "cd '$BACKEND_DIR' && APP_MODE='$MODE' DATABASE_URL='sqlite:///$DB_PATH' ACCOUNT_COLLECTOR_DIR='$AGENT_DIR' PYTHONPATH='$BACKEND_DIR' '$PROJECT/.venv/bin/uvicorn' api.main:app --host 127.0.0.1 --port $BACKEND_PORT"
  sleep 3
fi

if port_in_use "$FRONTEND_PORT"; then
  echo "Frontend deja en cours sur $FRONTEND_PORT"
else
  echo "Demarrage frontend..."
  run_terminal \
    "finance-$MODE-frontend" \
    "cd '$FRONTEND_DIR' && APP_MODE='$MODE' NEXT_PUBLIC_APP_ENV='$APP_ENV' NEXT_PUBLIC_DATASET_LABEL='$DATASET_LABEL' NEXT_PUBLIC_API_URL='http://127.0.0.1:$BACKEND_PORT' $NEXT_COMMAND"
  sleep 5
fi

echo "URL: http://127.0.0.1:$FRONTEND_PORT"
echo "Si tu ouvres manuellement, evite localhost: utilise 127.0.0.1."
