#!/bin/bash
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="$PROJECT/runtime/local-prod"
BACKEND_DB="${FINANCE_TRACKER_SOURCE_DB:-$PROJECT/finance.db}"
RUNTIME_DB_CURRENT="$RUNTIME/data/current/finance.db"
RUNTIME_DB_ROLLBACK="$RUNTIME/data/rollback"
AGENT_DIR="$PROJECT/agents/account_collector"
COMMIT_SHA="$(git -C "$PROJECT" rev-parse HEAD)"
ALLOW_DIRTY="${1:-}"

echo "Promotion local-prod"
echo "Project:  $PROJECT"
echo "Runtime:  $RUNTIME"
echo "Commit:   $COMMIT_SHA"

if [ "$ALLOW_DIRTY" != "--allow-dirty" ] && { ! git -C "$PROJECT" diff --quiet || ! git -C "$PROJECT" diff --cached --quiet; }; then
  echo "Worktree non propre. Commit ou stash les changements avant promotion."
  echo "But: garantir que local-prod correspond a un commit identifiable."
  echo "Pour un test local non promouvable: scripts/promote_local_prod.sh --allow-dirty"
  exit 1
fi

if [ "$ALLOW_DIRTY" = "--allow-dirty" ]; then
  echo "ATTENTION: promotion de test avec worktree non propre."
  echo "Ne pas considerer ce runtime comme une prod valide issue d'un commit."
fi

echo "Verification agent..."
(
  cd "$PROJECT/agents/account_collector"
  PYTHONPATH=. ../../.venv/bin/pytest
)

echo "Verification backend..."
(
  cd "$PROJECT"
  .venv/bin/pytest backend/tests
)

echo "Verification frontend..."
(
  cd "$PROJECT/frontend"
  npm run lint
  npx tsc --noEmit
)

echo "Build frontend local-prod..."
(
  cd "$PROJECT/frontend"
  APP_MODE=local-prod \
  NEXT_PUBLIC_APP_ENV=local-prod \
  NEXT_PUBLIC_DATASET_LABEL="Base locale prod" \
  NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 \
  npm run build -- --webpack
)

echo "Preparation runtime..."
mkdir -p "$RUNTIME"/{backend,frontend,agents/account_collector,logs}
mkdir -p "$RUNTIME/data/current" "$RUNTIME_DB_ROLLBACK"

echo "Copie backend minimal..."
rsync -a --delete \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  "$PROJECT/backend/api" \
  "$PROJECT/backend/core" \
  "$PROJECT/backend/db" \
  "$PROJECT/backend/requirements.txt" \
  "$RUNTIME/backend/"

echo "Copie frontend build..."
rsync -a --delete \
  "$PROJECT/frontend/.next-local-prod" \
  "$PROJECT/frontend/package.json" \
  "$PROJECT/frontend/package-lock.json" \
  "$PROJECT/frontend/next.config.ts" \
  "$PROJECT/frontend/public" \
  "$RUNTIME/frontend/"
ln -sfn "$PROJECT/frontend/node_modules" "$RUNTIME/frontend/node_modules"

echo "Copie agent collector minimal..."
rsync -a --delete \
  --exclude ".pytest_cache/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  "$AGENT_DIR/account_collector" \
  "$AGENT_DIR/config" \
  "$RUNTIME/agents/account_collector/"

if [ ! -f "$RUNTIME_DB_CURRENT" ]; then
  echo "Initialisation DB prod runtime depuis $BACKEND_DB"
  cp "$BACKEND_DB" "$RUNTIME_DB_CURRENT"
else
  BACKUP="$RUNTIME_DB_ROLLBACK/finance.$(date +%Y%m%d_%H%M%S).db.bak"
  echo "Backup DB runtime existante: $BACKUP"
  cp "$RUNTIME_DB_CURRENT" "$BACKUP"
fi

cat > "$RUNTIME/VERSION" <<EOF
commit=$COMMIT_SHA
dirty_allowed=$([ "$ALLOW_DIRTY" = "--allow-dirty" ] && echo "true" || echo "false")
promoted_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
frontend_api=http://127.0.0.1:8100
backend_db=$RUNTIME_DB_CURRENT
rollback_dir=$RUNTIME_DB_ROLLBACK
EOF

cat <<EOF

Promotion preparee.

Runtime: $RUNTIME
Version: $RUNTIME/VERSION

Prochaine etape:
- demarrer avec: ./launcher.sh local-prod
EOF
