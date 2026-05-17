import argparse
from datetime import date

from core.provider_duplicate_reconciler import reconcile_provider_duplicates
from db.database import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date-from", type=date.fromisoformat)
    parser.add_argument("--date-to", type=date.fromisoformat)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = reconcile_provider_duplicates(
            db=db,
            provider="powens",
            date_from=args.date_from,
            date_to=args.date_to,
            apply=args.apply,
        )
        print(f"candidates={len(result.candidates)} applied={result.applied}")
        for candidate in result.candidates:
            print({
                "provider_tx_id": candidate.provider_transaction_id,
                "delete_powens_local_id": candidate.provider_transaction_local_id,
                "keep_existing_local_id": candidate.existing_transaction_id,
                "account": candidate.account_name,
                "date": candidate.date.isoformat(),
                "amount": candidate.amount,
                "type": candidate.transaction_type,
                "provider_label": candidate.provider_label,
                "existing_label": candidate.existing_label,
            })
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
