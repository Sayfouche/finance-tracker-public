# Open Banking Provider Notes

This directory documents adapter design, not personal provider access.

For public work:

- use mock fixtures for tests;
- store real provider credentials in environment variables;
- store real account mappings in ignored private config files;
- never commit OAuth tokens, account ids, IBANs, balances, or transaction
  payloads from a real institution.

The concrete provider implementation should map provider-specific account and
transaction responses into the internal collector contract defined in
`account_collector/models.py`.
