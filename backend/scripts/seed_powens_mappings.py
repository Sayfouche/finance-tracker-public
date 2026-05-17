from db.database import SessionLocal
from db.models import Account, AccountProviderMapping


MAPPINGS = [
    ("1", "CC Demo Bank B", "Compte Demo B Alex", "courant", "EUR"),
    ("2", "Compte Demo A", "Compte Demo A Alex", "courant", "EUR"),
    ("3", "Livret Reserve A", "LDDS Alex", "livret", "EUR"),
    ("4", "Livret Reserve B", "LDDS Madame", "livret", "EUR"),
    ("5", "Livret Demo B", "Livret A", "livret", "EUR"),
    ("6", "Prêt immo", "Crédit immobilier", "credit", "EUR"),
]


def main() -> int:
    db = SessionLocal()
    try:
        created = updated = 0
        for provider_account_id, account_name, external_name, external_type, currency in MAPPINGS:
            account = db.query(Account).filter_by(name=account_name).first()
            if account is None:
                raise RuntimeError(f"local account not found: {account_name}")

            mapping = (
                db.query(AccountProviderMapping)
                .filter_by(provider="powens", provider_account_id=provider_account_id)
                .first()
            )
            if mapping is None:
                db.add(AccountProviderMapping(
                    provider="powens",
                    provider_account_id=provider_account_id,
                    local_account_id=account.id,
                    external_name=external_name,
                    external_type=external_type,
                    currency=currency,
                    active=True,
                ))
                created += 1
            else:
                mapping.local_account_id = account.id
                mapping.external_name = external_name
                mapping.external_type = external_type
                mapping.currency = currency
                mapping.active = True
                updated += 1

        db.commit()
        print(f"powens mappings ready: created={created}, updated={updated}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
