# Agent Industrialization Notes

The account collector can be industrialized as a local ingestion pipeline:

1. Collect accounts from a provider adapter or manual file.
2. Normalize balances and transactions.
3. Stage the run for review.
4. Import accepted changes into the local database.
5. Keep provider raw payloads and credentials outside Git.

Public fixtures should remain synthetic. Real provider state, tokens and account
mapping files belong in ignored private paths.
