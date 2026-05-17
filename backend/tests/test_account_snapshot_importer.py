import json
from datetime import date

from core.account_snapshot_importer import import_account_snapshot
from db.models import (
    Account,
    AccountProviderMapping,
    AccountType,
    AgentRun,
    AgentRunError,
    AgentRunStatus,
    ExternalTransaction,
    FamilyMember,
    MemberRole,
    PatrimonyDraftItem,
    PatrimonySnapshot,
    Transaction,
    TransactionType,
)


def _make_account(db, name: str = "Compte Demo B") -> Account:
    member = FamilyMember(first_name="Alex", role=MemberRole.owner)
    db.add(member)
    db.flush()
    account = Account(name=name, type=AccountType.courant, bank="Demo Bank B")
    account.members = [member]
    db.add(account)
    db.flush()
    return account


def _write_snapshot(tmp_path, accounts):
    path = tmp_path / "snapshot.json"
    path.write_text(
        json.dumps({
            "snapshot_date": "2026-05-12T12:00:00+00:00",
            "source": "account_collector",
            "run_id": "powens-2026-05-12",
            "accounts": accounts,
            "errors": [],
        }),
        encoding="utf-8",
    )
    return path


def _account_payload(external_id: str = "1"):
    return {
        "external_id": external_id,
        "institution": "Demo Bank B",
        "account_name": "Compte Demo B Alex",
        "account_type": "courant",
        "currency": "EUR",
        "balance": 219.96,
        "balance_date": "2026-05-12",
        "collection_strategy": "powens",
        "status": "success",
        "transactions": [
            {
                "date": "2026-05-11",
                "label": "CARREFOUR MARKET",
                "amount": -12.5,
                "currency": "EUR",
                "external_id": "tx-1",
            },
            {
                "date": "2026-05-10",
                "label": "SALAIRE",
                "amount": 2500.0,
                "currency": "EUR",
                "external_id": "tx-2",
            },
        ],
    }


def test_import_account_snapshot_creates_transactions_and_patrimony_draft(db, tmp_path):
    account = _make_account(db)
    db.add(AccountProviderMapping(
        provider="powens",
        provider_account_id="1",
        local_account_id=account.id,
    ))
    db.commit()
    snapshot = _write_snapshot(tmp_path, [_account_payload()])

    result = import_account_snapshot(
        db,
        snapshot,
        date_from=date(2026, 1, 1),
        date_to=date(2026, 5, 13),
    )

    assert result.status == AgentRunStatus.success
    assert result.balances_upserted == 1
    assert result.transactions_created == 2
    assert db.query(Transaction).count() == 2

    debit = db.query(Transaction).filter_by(transaction_type=TransactionType.debit).one()
    credit = db.query(Transaction).filter_by(transaction_type=TransactionType.credit).one()
    assert debit.amount == 12.5
    assert credit.amount == 2500.0
    assert db.query(ExternalTransaction).count() == 2

    assert db.query(PatrimonySnapshot).count() == 0
    draft = db.query(PatrimonyDraftItem).filter_by(account_id=account.id, month="2026-05").one()
    assert draft.value == 219.96

    run = db.query(AgentRun).get(result.run_id)
    assert run.provider == "powens"
    assert run.transactions_count == 2
    assert run.date_from.isoformat() == "2026-01-01"


def test_import_account_snapshot_is_idempotent_for_provider_transactions(db, tmp_path):
    account = _make_account(db)
    db.add(AccountProviderMapping(
        provider="powens",
        provider_account_id="1",
        local_account_id=account.id,
    ))
    db.commit()
    snapshot = _write_snapshot(tmp_path, [_account_payload()])

    first = import_account_snapshot(db, snapshot)
    second = import_account_snapshot(db, snapshot)

    assert first.transactions_created == 2
    assert second.transactions_created == 0
    assert second.transactions_skipped == 2
    assert db.query(Transaction).count() == 2
    assert db.query(PatrimonySnapshot).count() == 0
    assert db.query(PatrimonyDraftItem).count() == 1


def test_import_account_snapshot_records_missing_mapping_error(db, tmp_path):
    snapshot = _write_snapshot(tmp_path, [_account_payload(external_id="missing")])

    result = import_account_snapshot(db, snapshot)

    assert result.status == AgentRunStatus.failed
    assert result.errors == 1
    assert db.query(Transaction).count() == 0
    assert db.query(PatrimonySnapshot).count() == 0
    assert db.query(PatrimonyDraftItem).count() == 0
    error = db.query(AgentRunError).one()
    assert error.code == "missing_account_mapping"
    assert error.provider_account_id == "missing"


def test_import_account_snapshot_updates_existing_draft_balance_without_touching_published_snapshot(db, tmp_path):
    account = _make_account(db)
    db.add(AccountProviderMapping(
        provider="powens",
        provider_account_id="1",
        local_account_id=account.id,
    ))
    db.add(PatrimonySnapshot(account_id=account.id, month="2026-05", value=1.0))
    db.add(PatrimonyDraftItem(account_id=account.id, month="2026-06", value=2.0))
    db.commit()
    snapshot = _write_snapshot(tmp_path, [_account_payload()])

    result = import_account_snapshot(db, snapshot)

    assert result.balances_upserted == 1
    assert db.query(PatrimonySnapshot).count() == 1
    assert db.query(PatrimonySnapshot).one().value == 1.0
    draft = db.query(PatrimonyDraftItem).filter_by(account_id=account.id, month="2026-06").one()
    assert draft.value == 219.96


def test_import_account_snapshot_creates_next_month_draft_from_latest_published(db, tmp_path):
    account = _make_account(db)
    db.add(AccountProviderMapping(
        provider="powens",
        provider_account_id="1",
        local_account_id=account.id,
    ))
    db.add(PatrimonySnapshot(account_id=account.id, month="2026-05", value=100.0))
    db.commit()
    snapshot = _write_snapshot(tmp_path, [_account_payload()])

    import_account_snapshot(db, snapshot)

    assert db.query(PatrimonySnapshot).filter_by(month="2026-05").one().value == 100.0
    draft = db.query(PatrimonyDraftItem).filter_by(account_id=account.id, month="2026-06").one()
    assert draft.source_month == "2026-05"
    assert draft.source_value == 100.0
    assert draft.value == 219.96
