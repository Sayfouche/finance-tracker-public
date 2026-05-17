from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from db.models import AgentImportDecision, AccountProviderMapping, ExternalTransaction, Transaction, TransactionType


@dataclass(frozen=True)
class AgentRunOutput:
    run_id: str
    provider: str
    snapshot_path: Path
    snapshot_date: datetime
    accounts_count: int
    transactions_count: int
    errors_count: int
    date_from: date | None
    date_to: date | None


def list_account_collector_outputs(base_dir: Path) -> list[AgentRunOutput]:
    outputs: dict[str, AgentRunOutput] = {}

    runs_dir = base_dir / "runs"
    if runs_dir.exists():
        for manifest_path in runs_dir.glob("*/manifest.json"):
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            snapshot_path = Path(payload["snapshot_path"])
            if not snapshot_path.is_absolute():
                snapshot_path = manifest_path.parent / snapshot_path
            if snapshot_path.exists():
                snapshot = _read_snapshot(snapshot_path)
                outputs[payload["run_id"]] = _output_from_snapshot(snapshot_path, snapshot)

    snapshots_dir = base_dir / "snapshots"
    if snapshots_dir.exists():
        for snapshot_path in snapshots_dir.glob("*.json"):
            try:
                snapshot = _read_snapshot(snapshot_path)
                output = _output_from_snapshot(snapshot_path, snapshot)
            except (KeyError, ValueError, json.JSONDecodeError):
                continue
            outputs.setdefault(output.run_id, output)

    return sorted(outputs.values(), key=lambda item: item.snapshot_date, reverse=True)


def get_account_collector_output(base_dir: Path, run_id: str) -> dict[str, Any]:
    for output in list_account_collector_outputs(base_dir):
        if output.run_id == run_id:
            return _read_snapshot(output.snapshot_path)
    raise ValueError(f"agent output not found: {run_id}")


def diff_account_collector_output(
    db: Session,
    base_dir: Path,
    run_id: str,
) -> dict[str, Any]:
    snapshot = get_account_collector_output(base_dir, run_id)
    provider = _snapshot_provider(snapshot)
    items: list[dict[str, Any]] = []
    summary = {"new": 0, "duplicate_candidate": 0, "already_imported": 0, "unmapped_account": 0, "error": 0}

    for account in snapshot.get("accounts", []):
        provider_account_id = str(account.get("external_id", "")).strip()
        mapping = (
            db.query(AccountProviderMapping)
            .filter_by(provider=provider, provider_account_id=provider_account_id, active=True)
            .first()
        )
        if not mapping:
            tx_count = len(account.get("transactions", []))
            summary["unmapped_account"] += tx_count
            items.extend([
                {
                    "item_id": build_item_id(provider, run_id, provider_account_id, tx),
                    "status": "unmapped_account",
                    "provider_account_id": provider_account_id,
                    "local_account_id": None,
                    "transaction": tx,
                    "matches": [],
                    "decision": _decision_for(db, run_id, build_item_id(provider, run_id, provider_account_id, tx)),
                }
                for tx in account.get("transactions", [])
            ])
            continue

        for tx in account.get("transactions", []):
            item_id = build_item_id(provider, run_id, provider_account_id, tx)
            external_transaction = _external_transaction_for(db, provider, tx)
            amount_signed = float(tx["amount"])
            tx_type = TransactionType.credit if amount_signed > 0 else TransactionType.debit
            if external_transaction:
                existing = db.get(Transaction, external_transaction.local_transaction_id)
                matches = [existing] if existing else []
                status = "already_imported"
            else:
                matches = (
                    db.query(Transaction)
                    .filter(
                        Transaction.account_id == mapping.local_account_id,
                        Transaction.date == date.fromisoformat(tx["date"][:10]),
                        Transaction.amount == abs(amount_signed),
                        Transaction.transaction_type == tx_type,
                    )
                    .all()
                )
                status = "duplicate_candidate" if matches else "new"
            summary[status] += 1
            items.append({
                "item_id": item_id,
                "status": status,
                "provider_account_id": provider_account_id,
                "local_account_id": mapping.local_account_id,
                "transaction": tx,
                "matches": [
                    {
                        "id": match.id,
                        "date": match.date.isoformat(),
                        "label": match.label,
                        "amount": match.amount,
                        "type": match.transaction_type.value,
                    }
                    for match in matches
                ],
                "decision": _decision_for(db, run_id, item_id),
            })

    return {"run_id": run_id, "provider": provider, "summary": summary, "items": items}


def build_item_id(provider: str, run_id: str, provider_account_id: str, tx: dict[str, Any]) -> str:
    external_id = str(tx.get("external_id") or "").strip()
    if external_id:
        raw = f"{provider}|{run_id}|{provider_account_id}|{external_id}"
    else:
        raw = "|".join([
            provider,
            run_id,
            provider_account_id,
            str(tx.get("date", ""))[:10],
            str(tx.get("amount", "")),
            str(tx.get("label", "")),
        ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _external_transaction_for(db: Session, provider: str, tx: dict[str, Any]) -> ExternalTransaction | None:
    external_id = str(tx.get("external_id") or "").strip()
    if not external_id:
        return None
    return (
        db.query(ExternalTransaction)
        .filter_by(provider=provider, provider_transaction_id=external_id)
        .first()
    )


def serialize_output(output: AgentRunOutput) -> dict[str, Any]:
    return {
        "run_id": output.run_id,
        "provider": output.provider,
        "snapshot_path": str(output.snapshot_path),
        "snapshot_date": output.snapshot_date.isoformat(),
        "accounts_count": output.accounts_count,
        "transactions_count": output.transactions_count,
        "errors_count": output.errors_count,
        "date_from": output.date_from.isoformat() if output.date_from else None,
        "date_to": output.date_to.isoformat() if output.date_to else None,
    }


def _read_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("accounts"), list):
        raise ValueError("not an account collector snapshot")
    return payload


def _output_from_snapshot(path: Path, snapshot: dict[str, Any]) -> AgentRunOutput:
    transactions = [
        tx
        for account in snapshot.get("accounts", [])
        for tx in account.get("transactions", [])
    ]
    tx_dates = [date.fromisoformat(tx["date"][:10]) for tx in transactions if tx.get("date")]
    return AgentRunOutput(
        run_id=snapshot["run_id"],
        provider=_snapshot_provider(snapshot),
        snapshot_path=path,
        snapshot_date=datetime.fromisoformat(snapshot["snapshot_date"]),
        accounts_count=len(snapshot.get("accounts", [])),
        transactions_count=len(transactions),
        errors_count=len(snapshot.get("errors", [])),
        date_from=min(tx_dates) if tx_dates else None,
        date_to=max(tx_dates) if tx_dates else None,
    )


def _snapshot_provider(snapshot: dict[str, Any]) -> str:
    accounts = snapshot.get("accounts", [])
    if accounts:
        strategy = accounts[0].get("collection_strategy")
        if isinstance(strategy, str) and strategy:
            return strategy
    return "unknown"


def _decision_for(db: Session, run_id: str, item_id: str) -> str | None:
    decision = (
        db.query(AgentImportDecision)
        .filter_by(agent_name="account_collector", run_id=run_id, item_id=item_id)
        .first()
    )
    return decision.decision.value if decision else None
