from datetime import date

from core.provider_duplicate_reconciler import reconcile_provider_duplicates
from db.models import (
    Account,
    AccountType,
    ExternalTransaction,
    FamilyMember,
    MemberRole,
    Transaction,
    TransactionType,
)


def _make_account(db):
    member = FamilyMember(first_name="Alex", role=MemberRole.owner)
    db.add(member)
    db.flush()
    account = Account(name="CC Test", type=AccountType.courant)
    account.members = [member]
    db.add(account)
    db.flush()
    return account


def _make_tx(db, account, label, import_hash):
    tx = Transaction(
        account_id=account.id,
        date=date(2026, 5, 4),
        raw_label=label,
        label=label.lower(),
        amount=200.0,
        transaction_type=TransactionType.debit,
        import_hash=import_hash,
    )
    db.add(tx)
    db.flush()
    return tx


def test_reconcile_provider_duplicates_dry_run_does_not_modify(db):
    account = _make_account(db)
    existing = _make_tx(db, account, "vir inst demo household", "manual")
    provider = _make_tx(db, account, "inst demo household", "powens")
    db.add(ExternalTransaction(
        provider="powens",
        provider_transaction_id="ptx-1",
        provider_account_id="1",
        local_transaction_id=provider.id,
    ))
    db.commit()

    result = reconcile_provider_duplicates(db, provider="powens", apply=False)

    assert len(result.candidates) == 1
    assert db.get(Transaction, provider.id) is not None
    assert db.query(ExternalTransaction).one().local_transaction_id == provider.id
    assert result.candidates[0].existing_transaction_id == existing.id


def test_reconcile_provider_duplicates_apply_repoints_external_and_deletes_provider_duplicate(db):
    account = _make_account(db)
    existing = _make_tx(db, account, "vir inst demo household", "manual")
    provider = _make_tx(db, account, "inst demo household", "powens")
    db.add(ExternalTransaction(
        provider="powens",
        provider_transaction_id="ptx-1",
        provider_account_id="1",
        local_transaction_id=provider.id,
    ))
    db.commit()

    result = reconcile_provider_duplicates(db, provider="powens", apply=True)

    assert len(result.candidates) == 1
    assert db.get(Transaction, provider.id) is None
    assert db.get(Transaction, existing.id) is not None
    assert db.query(ExternalTransaction).one().local_transaction_id == existing.id
