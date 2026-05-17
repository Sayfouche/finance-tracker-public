from datetime import date

import pytest

from account_collector.models import AccountType, CollectionSnapshot, CollectionStatus


def test_snapshot_from_dict_parses_accounts_and_transactions():
    snapshot = CollectionSnapshot.from_dict(
        {
            "snapshot_date": "2026-05-12T08:00:00+02:00",
            "source": "account_collector",
            "run_id": "test-run",
            "accounts": [
                {
                    "external_id": "demo-checking-1",
                    "institution": "Demo Bank A",
                    "account_name": "Compte courant Demo A",
                    "account_type": "courant",
                    "currency": "EUR",
                    "balance": 100.5,
                    "balance_date": "2026-05-12",
                    "collection_strategy": "manual_file",
                    "transactions": [
                        {
                            "date": "2026-05-10",
                            "label": "CARREFOUR",
                            "amount": -42.35
                        }
                    ]
                }
            ],
            "errors": []
        }
    )

    account = snapshot.accounts[0]
    assert account.external_id == "demo-checking-1"
    assert account.account_type == AccountType.courant
    assert account.status == CollectionStatus.success
    assert account.balance_date == date(2026, 5, 12)
    assert account.transactions[0].label == "CARREFOUR"
    assert account.transactions[0].currency == "EUR"


def test_snapshot_rejects_empty_accounts():
    with pytest.raises(ValueError, match="at least one account"):
        CollectionSnapshot.from_dict(
            {
                "snapshot_date": "2026-05-12T08:00:00+02:00",
                "source": "account_collector",
                "run_id": "test-run",
                "accounts": [],
                "errors": []
            }
        )


def test_account_rejects_invalid_type():
    with pytest.raises(ValueError):
        CollectionSnapshot.from_dict(
            {
                "snapshot_date": "2026-05-12T08:00:00+02:00",
                "source": "account_collector",
                "run_id": "test-run",
                "accounts": [
                    {
                        "external_id": "bad",
                        "institution": "Demo Bank A",
                        "account_name": "Bad",
                        "account_type": "unknown",
                        "currency": "EUR",
                        "balance": 0,
                        "balance_date": "2026-05-12",
                        "collection_strategy": "manual_file",
                        "transactions": []
                    }
                ],
                "errors": []
            }
        )
