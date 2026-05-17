# Specifications - Finance Tracker

Finance Tracker is a local-first personal finance application for importing
bank transactions, categorizing expenses, tracking account balances, and
monitoring net worth over time.

## Scope

- Manage household members and accounts dynamically.
- Import CSV or Excel transaction files.
- Categorize transactions with rules and manual overrides.
- Detect internal transfers so they do not distort income or expenses.
- Track monthly account snapshots and net worth.
- Provide a demo dataset for development and screenshots.

## Data Model

Main entities:

- `FamilyMember`: a person attached to one or more accounts.
- `Account`: current accounts, savings, investments, real estate, credit, or
  custom assets/passives.
- `Transaction`: normalized bank operations with category and flags.
- `Category` and `CategoryRule`: budgeting taxonomy and matching rules.
- `PatrimonySnapshot`: monthly account balance history.
- `Settings`: configurable assumptions for simulations and projections.

## Public Data Policy

The public repository must not include:

- SQLite databases, exports, backups, or generated snapshots.
- Personal account names, real bank mappings, IBANs, balances, or transactions.
- Provider tokens, secrets, credentials, or OAuth artifacts.
- Private one-shot migration scripts tied to a personal spreadsheet.

Use the bundled demo seed for public examples. Keep private datasets in ignored
paths such as `runtime/`, `backups/`, `backend/private/`, `docs/private/`, or
`agents/account_collector/secrets/`.

## Demo Mode

`backend/scripts/seed_demo_data.py` creates a synthetic dataset with fictitious
members, accounts, transactions, and snapshots. It is safe to use for local
development, screenshots, and tests.

## Deployment

The app is designed for local use:

- Backend: FastAPI + SQLite.
- Frontend: Next.js + TypeScript.
- Runtime databases are configured with `DATABASE_URL`.

For public clones, start with demo data. For real use, create accounts through
the UI and import local files without committing generated data.
