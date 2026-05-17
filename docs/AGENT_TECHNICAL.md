# Account Collector Agent - Technical Notes

The account collector is a local, read-only ingestion agent. It does not write
directly to the Finance Tracker database. It collects account data, normalizes it
into a stable JSON contract, writes a snapshot file, and lets the main app stage
and review the result.

## Goals

- Keep provider-specific logic outside the main backend.
- Support manual fixtures, mock providers and real provider adapters.
- Produce deterministic snapshots for review and tests.
- Avoid committing credentials, raw real payloads or generated snapshots.

## Directory Layout

```text
agents/account_collector/
  account_collector/
    cli.py
    config.py
    models.py
    normalizer.py
    snapshot_writer.py
    connectors/
      base.py
      manual_file.py
      aggregator_mock.py
      open_banking.py
      powens.py
  config/
    accounts.example.json
    accounts.powens.json
  fixtures/
  tests/
```

Generated and private paths are ignored:

- `snapshots/`
- `secrets/`
- `runs/`
- `.env`
- `config/accounts.private*.json`

## Provider Contract

Connectors implement the interface from `connectors/base.py` and return
normalized account snapshots.

Each collected account includes:

- `external_id`: provider or configured account identifier;
- `institution`: provider institution label;
- `account_name`: display name;
- `account_type`: app-compatible type;
- `currency`;
- `balance`;
- `balance_date`;
- `collection_strategy`;
- `status`;
- `transactions`.

Each transaction includes:

- date;
- label;
- signed amount;
- currency;
- optional external transaction id.

## CLI Commands

Run from `agents/account_collector`.

Validate a snapshot:

```bash
python -m account_collector validate snapshots/latest.json
```

Collect from a manual JSON fixture:

```bash
python -m account_collector collect \
  --provider manual_file \
  --input fixtures/manual_sample.json \
  --output snapshots/latest.json
```

Collect from the aggregator mock:

```bash
python -m account_collector collect \
  --provider aggregator_mock \
  --config config/accounts.example.json \
  --fixture fixtures/aggregator_mock_accounts.json \
  --output snapshots/aggregator_mock.json
```

Collect from a provider fixture:

```bash
python -m account_collector collect \
  --provider powens_fixture \
  --config config/accounts.example.json \
  --fixture fixtures/powens_accounts_transactions.json \
  --output snapshots/provider_fixture.json
```

## Real Provider Setup

Real provider use must stay local:

1. Copy `.env.example` to `.env`.
2. Fill provider credentials locally.
3. Store tokens under `secrets/`.
4. Store account mappings under `config/accounts.private.json`.
5. Write snapshots under `snapshots/`.

Do not commit any of those generated or private files.

## Main App Integration

The Finance Tracker backend reads agent output from a configured collector
directory. The staging flow compares a snapshot with local accounts and
transactions, then lets the user import or ignore changes.

Relevant backend modules:

- `backend/api/routes/agents.py`
- `backend/core/agent_staging.py`
- `backend/core/account_snapshot_importer.py`
- `backend/core/provider_duplicate_reconciler.py`

## Testing

Agent tests use only synthetic fixtures:

```bash
cd agents/account_collector
python -m pytest
```

Backend staging tests are in `backend/tests/test_agents_routes.py` and related
files.

## Security Notes

- Treat provider raw payloads as sensitive.
- Avoid logging credentials, tokens or full account identifiers.
- Keep OAuth artifacts out of Git.
- Prefer mock fixtures for public bug reports.
- Review generated snapshots before importing them into the main database.
