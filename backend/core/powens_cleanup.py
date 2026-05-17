from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from db.models import (
    AgentRun,
    AgentRunError,
    ExternalTransaction,
    PatrimonySnapshot,
    Transaction,
)


@dataclass(frozen=True)
class PowensCleanupResult:
    backup_path: Path
    transactions: int
    external_transactions: int
    patrimony_snapshots: int
    agent_runs: int
    agent_run_errors: int
    applied: bool


def cleanup_powens_imports(
    db: Session,
    backup_dir: Path,
    apply: bool = False,
) -> PowensCleanupResult:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"powens_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    external_rows = db.query(ExternalTransaction).filter_by(provider="powens").all()
    transaction_ids = [row.local_transaction_id for row in external_rows]
    transactions = (
        db.query(Transaction)
        .filter(Transaction.id.in_(transaction_ids))
        .all()
        if transaction_ids
        else []
    )
    snapshots = (
        db.query(PatrimonySnapshot)
        .filter(PatrimonySnapshot.note.like("Imported from powens%"))
        .all()
    )
    runs = db.query(AgentRun).filter_by(provider="powens").all()
    run_ids = [run.id for run in runs]
    run_errors = (
        db.query(AgentRunError)
        .filter(AgentRunError.run_id.in_(run_ids))
        .all()
        if run_ids
        else []
    )

    backup = {
        "created_at": datetime.now().isoformat(),
        "applied": apply,
        "transactions": [_transaction_to_dict(tx) for tx in transactions],
        "external_transactions": [_external_transaction_to_dict(row) for row in external_rows],
        "patrimony_snapshots": [_snapshot_to_dict(snapshot) for snapshot in snapshots],
        "agent_runs": [_agent_run_to_dict(run) for run in runs],
        "agent_run_errors": [_agent_run_error_to_dict(error) for error in run_errors],
    }
    backup_path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")

    if apply:
        for row in external_rows:
            db.delete(row)
        for tx in transactions:
            db.delete(tx)
        for snapshot in snapshots:
            db.delete(snapshot)
        for error in run_errors:
            db.delete(error)
        for run in runs:
            db.delete(run)
        db.commit()

    return PowensCleanupResult(
        backup_path=backup_path,
        transactions=len(transactions),
        external_transactions=len(external_rows),
        patrimony_snapshots=len(snapshots),
        agent_runs=len(runs),
        agent_run_errors=len(run_errors),
        applied=apply,
    )


def _transaction_to_dict(tx: Transaction) -> dict[str, Any]:
    return {
        "id": tx.id,
        "account_id": tx.account_id,
        "date": tx.date.isoformat(),
        "raw_label": tx.raw_label,
        "label": tx.label,
        "amount": tx.amount,
        "transaction_type": tx.transaction_type.value,
        "category_id": tx.category_id,
        "category_source": tx.category_source,
        "is_internal_transfer": tx.is_internal_transfer,
        "is_neutral": tx.is_neutral,
        "is_investment": tx.is_investment,
        "is_compte_pro": tx.is_compte_pro,
        "transfer_pair_id": tx.transfer_pair_id,
        "import_hash": tx.import_hash,
    }


def _external_transaction_to_dict(row: ExternalTransaction) -> dict[str, Any]:
    return {
        "id": row.id,
        "provider": row.provider,
        "provider_transaction_id": row.provider_transaction_id,
        "provider_account_id": row.provider_account_id,
        "local_transaction_id": row.local_transaction_id,
        "raw_payload_json": row.raw_payload_json,
    }


def _snapshot_to_dict(snapshot: PatrimonySnapshot) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "account_id": snapshot.account_id,
        "month": snapshot.month,
        "value": snapshot.value,
        "note": snapshot.note,
    }


def _agent_run_to_dict(run: AgentRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "agent_name": run.agent_name,
        "provider": run.provider,
        "external_run_id": run.external_run_id,
        "status": run.status.value,
        "date_from": run.date_from.isoformat() if run.date_from else None,
        "date_to": run.date_to.isoformat() if run.date_to else None,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat(),
        "accounts_count": run.accounts_count,
        "transactions_count": run.transactions_count,
        "snapshot_path": run.snapshot_path,
        "message": run.message,
    }


def _agent_run_error_to_dict(error: AgentRunError) -> dict[str, Any]:
    return {
        "id": error.id,
        "run_id": error.run_id,
        "provider_account_id": error.provider_account_id,
        "severity": error.severity,
        "code": error.code,
        "message": error.message,
        "raw_payload_json": error.raw_payload_json,
    }
