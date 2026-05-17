# Local Deployment

## Demo Mode

```bash
./launcher.sh dev
```

The launcher creates a demo SQLite database under `runtime/dev/` if needed.

## Manual Backend

```bash
cd backend
DATABASE_URL=sqlite:///./finance.demo.db ../.venv/bin/python -m scripts.seed_demo_data
DATABASE_URL=sqlite:///./finance.demo.db PYTHONPATH=. ../.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
```

## Manual Frontend

```bash
cd frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

## Private Data

Use ignored paths for real databases, exports, provider credentials, account
mappings, and generated snapshots. Do not commit runtime data.
