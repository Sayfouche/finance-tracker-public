import json
from datetime import date

from core.agent_staging import diff_account_collector_output, list_account_collector_outputs
from db.models import (
    Account,
    AccountProviderMapping,
    AccountType,
    ExternalTransaction,
    FamilyMember,
    MemberRole,
    Transaction,
    TransactionType,
)


def _write_snapshot(root):
    snapshots = root / "snapshots"
    snapshots.mkdir()
    path = snapshots / "powens-test.json"
    path.write_text(
        json.dumps({
            "snapshot_date": "2026-05-12T12:00:00+00:00",
            "source": "account_collector",
            "run_id": "powens-test",
            "accounts": [
                {
                    "external_id": "1",
                    "collection_strategy": "powens",
                    "transactions": [
                        {"date": "2026-05-11", "label": "A", "amount": -10.0, "external_id": "a"},
                        {"date": "2026-05-12", "label": "B", "amount": 20.0, "external_id": "b"},
                    ],
                }
            ],
            "errors": [],
        }),
        encoding="utf-8",
    )
    return path


def test_list_account_collector_outputs_from_snapshots(tmp_path):
    _write_snapshot(tmp_path)

    outputs = list_account_collector_outputs(tmp_path)

    assert len(outputs) == 1
    assert outputs[0].run_id == "powens-test"
    assert outputs[0].transactions_count == 2
    assert outputs[0].date_from.isoformat() == "2026-05-11"
    assert outputs[0].date_to.isoformat() == "2026-05-12"


def test_diff_account_collector_output_marks_new_duplicate_and_unmapped(db, tmp_path):
    _write_snapshot(tmp_path)
    member = FamilyMember(first_name="Alex", role=MemberRole.owner)
    db.add(member)
    db.flush()
    account = Account(name="CC", type=AccountType.courant)
    account.members = [member]
    db.add(account)
    db.flush()
    db.add(AccountProviderMapping(
        provider="powens",
        provider_account_id="1",
        local_account_id=account.id,
    ))
    db.add(Transaction(
        account_id=account.id,
        date=date(2026, 5, 11),
        raw_label="A",
        label="a",
        amount=10.0,
        transaction_type=TransactionType.debit,
        import_hash="manual-a",
    ))
    db.commit()

    diff = diff_account_collector_output(db, tmp_path, "powens-test")

    assert diff["summary"]["duplicate_candidate"] == 1
    assert diff["summary"]["new"] == 1


def test_diff_account_collector_output_marks_provider_transaction_as_already_imported(db, tmp_path):
    _write_snapshot(tmp_path)
    member = FamilyMember(first_name="Alex", role=MemberRole.owner)
    db.add(member)
    db.flush()
    account = Account(name="CC", type=AccountType.courant)
    account.members = [member]
    db.add(account)
    db.flush()
    db.add(AccountProviderMapping(
        provider="powens",
        provider_account_id="1",
        local_account_id=account.id,
    ))
    tx = Transaction(
        account_id=account.id,
        date=date(2026, 5, 10),
        raw_label="A previous date",
        label="a previous date",
        amount=10.0,
        transaction_type=TransactionType.debit,
        import_hash="provider-a",
    )
    db.add(tx)
    db.flush()
    db.add(ExternalTransaction(
        provider="powens",
        provider_transaction_id="a",
        provider_account_id="1",
        local_transaction_id=tx.id,
    ))
    db.commit()

    diff = diff_account_collector_output(db, tmp_path, "powens-test")
    item = next(item for item in diff["items"] if item["transaction"]["external_id"] == "a")

    assert item["status"] == "already_imported"
    assert item["matches"][0]["id"] == tx.id
    assert diff["summary"]["already_imported"] == 1
    assert diff["summary"]["new"] == 1
