# Public Roadmap

## Completed Baseline

- FastAPI backend with SQLAlchemy models.
- Next.js frontend for dashboard, transactions, accounts, patrimony, settings,
  simulator, imports, and agent runs.
- Public-safe system seed for categories, rules, and settings.
- Demo seed with synthetic accounts, transactions, and balance snapshots.
- Dynamic account and member creation from the Accounts page.

## Next Product Work

- Improve account editing and archiving from the UI.
- Add import preview and validation workflows for more bank formats.
- Add configurable category rule management.
- Add explicit onboarding for first-run setup.
- Add more robust demo data generation across multiple months.
- Document provider integration patterns without committing provider-specific
  user mappings.

## Publication Checklist

- Publish from a clean repository without historical personal database commits.
- Keep `.db`, `.env`, backups, runtime files, snapshots, and secrets ignored.
- Use demo fixtures only.
- Keep private migration scripts and provider mappings outside Git.
- Run backend tests and `npm run build` before tagging a public release.
