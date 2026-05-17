# Account Collection Agent Notes

The account collector is an optional local workflow for importing balances and
recent transactions from provider adapters or manual files.

## Public Repository Rules

- Commit only mock fixtures and synthetic examples.
- Keep real provider mappings in ignored files such as
  `agents/account_collector/config/accounts.private.json`.
- Keep tokens and OAuth artifacts in `agents/account_collector/secrets/`.
- Keep generated snapshots in `agents/account_collector/snapshots/`.

## Supported Adapter Shapes

- `manual_file`: read a local JSON export in the collector contract.
- `aggregator_mock`: deterministic fixture-backed provider for tests.
- `open_banking` / `powens`: adapter structure for real providers, configured
  via environment variables and private account mapping files.

## Provider Contract

Each collected account should provide:

- external account id;
- institution name;
- account name and type;
- balance and balance date;
- optional normalized transactions.

Real provider coverage and pricing should be validated outside this repository.
