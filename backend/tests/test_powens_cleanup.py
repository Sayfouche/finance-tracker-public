import json
from datetime import date, datetime

from core.powens_cleanup import cleanup_powens_imports
from db.models import (
    AgentRun,
    AgentRunError,
    AgentRunStatus,
    ExternalTransaction,
    FamilyMember,
    Account,
    AccountType,
    MemberRole,
    PatrimonySnapshot,
    Transaction,
    TransactionType,
)


def _seed_powens_import(db):
    member = FamilyMember(first_name="Alex", role=MemberRole.owner)
    db.add(member)
    db.flush()
    account = Account(name="Compte Demo B", type=AccountType.courant)
    account.members = [member]
    db.add(account)
    db.flush()
    powens_tx = Transaction(
        account_id=account.id,
        date=date(2026, 5, 11),
        raw_label="CARREFOUR",
        label="carrefour",
        amount=12.5,
        transaction_type=TransactionType.debit,
        import_hash="powens",
    )
    manual_tx = Transaction(
        account_id=account.id,
        date=date(2026, 5, 12),
        raw_label="MANUAL",
        label="manual",
        amount=9.0,
        transaction_type=TransactionType.debit,
        import_hash="manual",
    )
    db.add_all([powens_tx, manual_tx])
    db.flush()
    db.add(ExternalTransaction(
        provider="powens",
        provider_transaction_id="tx-1",
        provider_account_id="1",
        local_transaction_id=powens_tx.id,
    ))
    db.add(PatrimonySnapshot(
        account_id=account.id,
        month="2026-05",
        value=100.0,
        note="Imported from powens run powens-2026-05-12",
    ))
    run = AgentRun(
        agent_name="account_collector",
        provider="powens",
        status=AgentRunStatus.success,
        started_at=datetime(2026, 5, 12, 12, 0, 0),
        finished_at=datetime(2026, 5, 12, 12, 1, 0),
    )
    db.add(run)
    db.flush()
    db.add(AgentRunError(run_id=run.id, code="x", message="error"))
    db.commit()


def test_cleanup_powens_imports_dry_run_preserves_data(db, tmp_path):
    _seed_powens_import(db)

    result = cleanup_powens_imports(db, tmp_path, apply=False)

    assert result.transactions == 1
    assert result.external_transactions == 1
    assert result.patrimony_snapshots == 1
    assert result.agent_runs == 1
    assert db.query(Transaction).count() == 2
    assert json.loads(result.backup_path.read_text(encoding="utf-8"))["applied"] is False


def test_cleanup_powens_imports_apply_removes_only_powens_import_data(db, tmp_path):
    _seed_powens_import(db)

    result = cleanup_powens_imports(db, tmp_path, apply=True)

    assert result.applied is True
    assert db.query(ExternalTransaction).count() == 0
    assert db.query(PatrimonySnapshot).count() == 0
    assert db.query(AgentRun).count() == 0
    assert db.query(AgentRunError).count() == 0
    remaining = db.query(Transaction).one()
    assert remaining.import_hash == "manual"
