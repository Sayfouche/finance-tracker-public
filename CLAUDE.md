# Finance Tracker

Local-first personal finance tracker.

## Public Safety

- Do not commit real databases, exports, backups, snapshots, tokens, or provider
  credentials.
- Keep private account mappings and one-shot migration scripts outside tracked
  files.
- Use `backend/scripts/seed_demo_data.py` for demo data.

## Project Layout

- `backend/`: FastAPI API, SQLAlchemy models, imports, categorization, tests.
- `frontend/`: Next.js app.
- `agents/account_collector/`: account collection adapter experiments and demo
  fixtures.
- `runtime/`: ignored local runtime data.

## Common Commands

```bash
cd backend && pytest
cd frontend && npm run build
./launcher.sh dev
```
