# Finance Tracker

Local-first personal finance tracker built with FastAPI, SQLite, Next.js and
TypeScript.

The app helps you import transactions, categorize expenses, track account
balances, monitor net worth, and run simple investment simulations. It ships
with synthetic demo data only.

## Features

- Dynamic account and household member setup.
- CSV / Excel transaction import.
- Rule-based categorization with manual overrides.
- Internal transfer detection.
- Monthly account snapshots and net-worth tracking.
- Budget category groups and rolling analytics.
- Demo account collector fixtures for provider integration experiments.

## Data Privacy

This repository is designed to be public-safe:

- no real SQLite database is committed;
- no `.env`, secrets, OAuth tokens, exports, snapshots or backups are committed;
- demo data is synthetic;
- private account mappings should stay in ignored files.

Before publishing forks, avoid committing files from `runtime/`, `backups/`,
`agents/account_collector/secrets/`, `agents/account_collector/snapshots/`, or
private provider config files.

## Quick Start

### Backend

```bash
cd backend
python -m venv ../.venv
../.venv/bin/pip install -r requirements.txt
DATABASE_URL=sqlite:///./finance.demo.db ../.venv/bin/python -m scripts.seed_demo_data
DATABASE_URL=sqlite:///./finance.demo.db PYTHONPATH=. ../.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000`.

## How to Use the App

See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for the main workflows:

- create household members and accounts;
- import transactions;
- categorize and review monthly budgets;
- maintain monthly patrimony snapshots;
- use the simulator;
- keep private financial data out of Git.

## Account Collector Agent

The optional account collector can collect synthetic/demo account snapshots from
fixtures or private provider adapters, then hand them to the main app for
staging.

See [docs/AGENT_TECHNICAL.md](docs/AGENT_TECHNICAL.md) for the CLI, provider
contract, staging flow and security rules.

## Tests

```bash
cd backend
../.venv/bin/pytest

cd ../frontend
npm run build
```

## Project Structure

- `backend/` - FastAPI API, SQLAlchemy models, import and categorization logic.
- `frontend/` - Next.js application.
- `agents/account_collector/` - optional account collection adapters and demo fixtures.
- `docs/` - public-safe notes and roadmap.

## License

No license has been selected yet.
