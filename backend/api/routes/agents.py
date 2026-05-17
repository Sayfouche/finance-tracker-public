import os
import hashlib
import json
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.agent_staging import (
    diff_account_collector_output,
    get_account_collector_output,
    list_account_collector_outputs,
    serialize_output,
)
from core.categorizer import categorize, normalize_label
from db.database import engine, get_db
from db.models import (
    AgentImportDecision,
    AgentImportDecisionValue,
    ExternalTransaction,
    Transaction,
    TransactionType,
)

router = APIRouter(prefix="/agents", tags=["agents"])


class ApplyDecisionBody(BaseModel):
    item_ids: list[str]
    decision: Literal["import", "ignore"]
    note: str | None = None


def _account_collector_dir() -> Path:
    configured = os.getenv("ACCOUNT_COLLECTOR_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "agents" / "account_collector"


def _project_root() -> Path:
    # En local-prod le backend tourne depuis runtime/local-prod/backend/ :
    # ACCOUNT_COLLECTOR_DIR pointe vers <project>/agents/account_collector → 2 niveaux au-dessus
    configured = os.getenv("ACCOUNT_COLLECTOR_DIR")
    if configured:
        return Path(configured).parent.parent
    return Path(__file__).resolve().parents[3]


def _collect_log_path() -> Path:
    return _project_root() / "runtime" / "local-prod" / "logs" / "collect_powens.log"


@router.get("/account-collector/runs")
def list_runs():
    outputs = list_account_collector_outputs(_account_collector_dir())
    return [serialize_output(output) for output in outputs]


@router.get("/account-collector/runs/{run_id}")
def get_run(run_id: str):
    return get_account_collector_output(_account_collector_dir(), run_id)


@router.get("/account-collector/runs/{run_id}/diff")
def get_run_diff(run_id: str, db: Session = Depends(get_db)):
    return diff_account_collector_output(db, _account_collector_dir(), run_id)


@router.post("/account-collector/runs/{run_id}/decisions")
def apply_run_decisions(
    run_id: str,
    body: ApplyDecisionBody,
    db: Session = Depends(get_db),
):
    if not body.item_ids:
        raise HTTPException(422, "Aucune ligne sélectionnée")

    requested = set(body.item_ids)
    diff = diff_account_collector_output(db, _account_collector_dir(), run_id)
    items = {item["item_id"]: item for item in diff["items"] if item["item_id"] in requested}
    missing = sorted(requested - set(items))
    if missing:
        raise HTTPException(404, {"message": "Certaines lignes n'existent pas dans ce run", "item_ids": missing})

    backup_path = _backup_sqlite_db() if body.decision == "import" else None
    imported: list[dict] = []
    ignored: list[str] = []
    skipped: list[dict] = []

    try:
        for item_id in requested:
            item = items[item_id]
            existing_decision = (
                db.query(AgentImportDecision)
                .filter_by(agent_name="account_collector", run_id=run_id, item_id=item_id)
                .first()
            )

            if body.decision == "ignore":
                _upsert_decision(
                    db=db,
                    existing=existing_decision,
                    provider=diff["provider"],
                    run_id=run_id,
                    item_id=item_id,
                    decision=AgentImportDecisionValue.ignored,
                    note=body.note,
                )
                ignored.append(item_id)
                continue

            if existing_decision and existing_decision.decision == AgentImportDecisionValue.imported:
                skipped.append({"item_id": item_id, "reason": "already_imported"})
                continue
            if item["status"] != "new":
                skipped.append({"item_id": item_id, "reason": f"not_new:{item['status']}"})
                continue
            if item["local_account_id"] is None:
                skipped.append({"item_id": item_id, "reason": "unmapped_account"})
                continue

            tx = _create_transaction_from_agent_item(db, diff["provider"], run_id, item)
            _upsert_decision(
                db=db,
                existing=existing_decision,
                provider=diff["provider"],
                run_id=run_id,
                item_id=item_id,
                decision=AgentImportDecisionValue.imported,
                note=body.note,
                local_transaction_id=tx.id,
            )
            imported.append({"item_id": item_id, "transaction_id": tx.id})

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "run_id": run_id,
        "decision": body.decision,
        "imported": imported,
        "ignored": ignored,
        "skipped": skipped,
        "backup_path": str(backup_path) if backup_path else None,
    }


def _create_transaction_from_agent_item(
    db: Session,
    provider: str,
    run_id: str,
    item: dict,
) -> Transaction:
    raw_tx = item["transaction"]
    amount_signed = float(raw_tx["amount"])
    tx_type = TransactionType.credit if amount_signed > 0 else TransactionType.debit
    tx_date = date.fromisoformat(raw_tx["date"][:10])
    raw_label = str(raw_tx.get("label") or raw_tx.get("raw_label") or "")
    label = normalize_label(raw_label)
    provider_transaction_id = str(raw_tx.get("external_id") or item["item_id"])

    existing_external = (
        db.query(ExternalTransaction)
        .filter_by(provider=provider, provider_transaction_id=provider_transaction_id)
        .first()
    )
    if existing_external:
        raise HTTPException(409, {"message": "Transaction provider déjà importée", "item_id": item["item_id"]})

    import_hash = hashlib.sha256(
        "|".join([
            "agent",
            provider,
            run_id,
            item["provider_account_id"],
            provider_transaction_id,
            str(item["local_account_id"]),
            tx_date.isoformat(),
            f"{abs(amount_signed):.2f}",
        ]).encode("utf-8")
    ).hexdigest()[:32]

    category_id = categorize(label, db)
    tx = Transaction(
        account_id=item["local_account_id"],
        date=tx_date,
        raw_label=raw_label,
        label=label,
        amount=abs(amount_signed),
        transaction_type=tx_type,
        category_id=category_id,
        category_source="auto" if category_id else None,
        import_hash=import_hash,
    )
    db.add(tx)
    db.flush()

    db.add(ExternalTransaction(
        provider=provider,
        provider_transaction_id=provider_transaction_id,
        provider_account_id=item["provider_account_id"],
        local_transaction_id=tx.id,
        raw_payload_json=json.dumps(raw_tx, ensure_ascii=False),
    ))
    return tx


def _upsert_decision(
    db: Session,
    existing: AgentImportDecision | None,
    provider: str,
    run_id: str,
    item_id: str,
    decision: AgentImportDecisionValue,
    note: str | None,
    local_transaction_id: int | None = None,
) -> AgentImportDecision:
    if existing:
        existing.decision = decision
        existing.note = note
        if local_transaction_id is not None:
            existing.local_transaction_id = local_transaction_id
        return existing

    created = AgentImportDecision(
        agent_name="account_collector",
        provider=provider,
        run_id=run_id,
        item_id=item_id,
        decision=decision,
        note=note,
        local_transaction_id=local_transaction_id,
    )
    db.add(created)
    return created


def _backup_sqlite_db() -> Path | None:
    if engine.url.get_backend_name() != "sqlite":
        return None
    database = engine.url.database
    if not database or database == ":memory:":
        return None
    db_path = Path(database)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    if not db_path.exists():
        return None
    backup_dir = db_path.parent.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f"finance_before_agent_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(db_path, backup_path)
    return backup_path


@router.post("/account-collector/collect")
def trigger_collect():
    script = _project_root() / "scripts" / "collect_powens.sh"
    if not script.exists():
        raise HTTPException(404, "Script collect_powens.sh introuvable")
    env_file = _account_collector_dir() / ".env"
    if not env_file.exists():
        raise HTTPException(400, "Fichier .env Powens absent — configure les credentials avant de lancer")
    log_path = _collect_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        ["/bin/bash", str(script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {"status": "started"}


@router.get("/account-collector/logs")
def get_collect_logs(lines: int = Query(default=100, ge=1, le=500)):
    log_path = _collect_log_path()
    if not log_path.exists():
        return {"lines": [], "exists": False, "total_lines": 0}
    content = log_path.read_text(encoding="utf-8", errors="replace")
    all_lines = content.splitlines()
    return {"lines": all_lines[-lines:], "exists": True, "total_lines": len(all_lines)}
