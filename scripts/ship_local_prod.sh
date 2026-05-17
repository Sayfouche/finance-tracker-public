#!/bin/bash
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="$PROJECT/runtime/local-prod"
LOG_DIR="$RUNTIME/logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_PID="$LOG_DIR/backend.pid"
FRONTEND_PID="$LOG_DIR/frontend.pid"
BACKEND_URL="http://127.0.0.1:8100"
FRONTEND_URL="http://127.0.0.1:3100"
BACKEND_LABEL="com.finance-tracker.local-prod.backend"
FRONTEND_LABEL="com.finance-tracker.local-prod.frontend"
BACKEND_SCREEN="finance-local-prod-backend"
FRONTEND_SCREEN="finance-local-prod-frontend"
HEAD_SHA="$(git -C "$PROJECT" rev-parse HEAD)"
UPSTREAM="$(git -C "$PROJECT" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"

echo "Ship local-prod"
echo "Project: $PROJECT"
echo "Commit:  $HEAD_SHA"

if [ -z "$UPSTREAM" ]; then
  echo "Aucun upstream Git configure pour la branche courante."
  echo "Configure l'upstream avant de shipper local-prod."
  exit 1
fi

if ! git -C "$PROJECT" diff --quiet || ! git -C "$PROJECT" diff --cached --quiet; then
  echo "Worktree non propre. Commit ou stash les changements avant ship."
  exit 1
fi

git -C "$PROJECT" fetch --quiet

LOCAL_SHA="$(git -C "$PROJECT" rev-parse HEAD)"
REMOTE_SHA="$(git -C "$PROJECT" rev-parse "$UPSTREAM")"
BASE_SHA="$(git -C "$PROJECT" merge-base HEAD "$UPSTREAM")"

if [ "$LOCAL_SHA" != "$REMOTE_SHA" ]; then
  echo "HEAD n'est pas synchronise avec $UPSTREAM."
  echo "local:  $LOCAL_SHA"
  echo "remote: $REMOTE_SHA"
  if [ "$LOCAL_SHA" = "$BASE_SHA" ]; then
    echo "La branche locale est en retard. Pull/rebase avant de shipper."
  elif [ "$REMOTE_SHA" = "$BASE_SHA" ]; then
    echo "La branche locale est en avance. Push avant de shipper."
  else
    echo "La branche locale et le remote ont diverge."
  fi
  exit 1
fi

echo "Promotion..."
"$PROJECT/scripts/promote_local_prod.sh"

if ! git -C "$PROJECT" diff --quiet -- frontend/tsconfig.json; then
  echo "Restauration frontend/tsconfig.json apres ajustement automatique Next..."
  git -C "$PROJECT" checkout -- frontend/tsconfig.json
fi

echo "Arret local-prod existant..."
if command -v launchctl >/dev/null 2>&1; then
  launchctl bootout "gui/$(id -u)" "$LOG_DIR/$BACKEND_LABEL.plist" >/dev/null 2>&1 || true
  launchctl bootout "gui/$(id -u)" "$LOG_DIR/$FRONTEND_LABEL.plist" >/dev/null 2>&1 || true
fi
if command -v screen >/dev/null 2>&1; then
  screen -S "$BACKEND_SCREEN" -X quit >/dev/null 2>&1 || true
  screen -S "$FRONTEND_SCREEN" -X quit >/dev/null 2>&1 || true
fi
"$PROJECT/scripts/stop_local.sh" local-prod
sleep 2

mkdir -p "$LOG_DIR"
: > "$BACKEND_LOG"
: > "$FRONTEND_LOG"

if command -v screen >/dev/null 2>&1; then
  echo "Demarrage backend local-prod via screen..."
  screen -dmS "$BACKEND_SCREEN" bash -lc \
    "cd '$RUNTIME/backend' && exec env APP_MODE='local-prod' DATABASE_URL='sqlite:///$RUNTIME/data/current/finance.db' ACCOUNT_COLLECTOR_DIR='$PROJECT/agents/account_collector' PYTHONPATH='$RUNTIME/backend' '$PROJECT/.venv/bin/uvicorn' api.main:app --host 127.0.0.1 --port 8100 >> '$BACKEND_LOG' 2>&1"

  echo "Demarrage frontend local-prod via screen..."
  screen -dmS "$FRONTEND_SCREEN" bash -lc \
    "cd '$RUNTIME/frontend' && exec env APP_MODE='local-prod' NEXT_PUBLIC_APP_ENV='local-prod' NEXT_PUBLIC_DATASET_LABEL='Base locale prod' NEXT_PUBLIC_API_URL='$BACKEND_URL' '$PROJECT/frontend/node_modules/.bin/next' start --hostname 127.0.0.1 --port 3100 >> '$FRONTEND_LOG' 2>&1"
else
  echo "Demarrage backend local-prod via nohup..."
  nohup bash -c 'cd "$1" && shift && exec "$@"' _ \
    "$RUNTIME/backend" \
    env \
    APP_MODE="local-prod" \
    DATABASE_URL="sqlite:///$RUNTIME/data/current/finance.db" \
    ACCOUNT_COLLECTOR_DIR="$PROJECT/agents/account_collector" \
    PYTHONPATH="$RUNTIME/backend" \
    "$PROJECT/.venv/bin/uvicorn" api.main:app --host 127.0.0.1 --port 8100 \
    >> "$BACKEND_LOG" 2>&1 &
  echo $! > "$BACKEND_PID"

  echo "Demarrage frontend local-prod via nohup..."
  nohup bash -c 'cd "$1" && shift && exec "$@"' _ \
    "$RUNTIME/frontend" \
    env \
    APP_MODE="local-prod" \
    NEXT_PUBLIC_APP_ENV="local-prod" \
    NEXT_PUBLIC_DATASET_LABEL="Base locale prod" \
    NEXT_PUBLIC_API_URL="$BACKEND_URL" \
    "$PROJECT/frontend/node_modules/.bin/next" start --hostname 127.0.0.1 --port 3100 \
    >> "$FRONTEND_LOG" 2>&1 &
  echo $! > "$FRONTEND_PID"
fi

wait_for_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-40}"
  local code

  for _ in $(seq 1 "$attempts"); do
    code="$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)"
    if [ "$code" = "200" ]; then
      echo "$label OK ($url)"
      return 0
    fi
    sleep 1
  done

  echo "$label ne repond pas en 200: $url"
  echo "Backend log:  $BACKEND_LOG"
  echo "Frontend log: $FRONTEND_LOG"
  return 1
}

wait_for_http "$BACKEND_URL/health" "Backend"
wait_for_http "$FRONTEND_URL" "Frontend"

lsof -ti ":8100" > "$BACKEND_PID" 2>/dev/null || true
lsof -ti ":3100" > "$FRONTEND_PID" 2>/dev/null || true

VERSION_COMMIT="$(grep '^commit=' "$RUNTIME/VERSION" | cut -d= -f2)"
if [ "$VERSION_COMMIT" != "$HEAD_SHA" ]; then
  echo "VERSION mismatch."
  echo "HEAD:    $HEAD_SHA"
  echo "VERSION: $VERSION_COMMIT"
  exit 1
fi

cat <<EOF

local-prod deploye.
URL: $FRONTEND_URL
Backend: $BACKEND_URL
Version: $VERSION_COMMIT
Logs:
- $BACKEND_LOG
- $FRONTEND_LOG
EOF
