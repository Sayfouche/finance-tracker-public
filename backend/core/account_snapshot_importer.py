"""
Import des snapshots produits par l'agent account_collector.

Le module reste volontairement indépendant du package agent: il consomme le
contrat JSON normalisé, puis écrit dans les tables métier du backend.
"""
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from core.categorizer import categorize, normalize_label
from core.transfer_detector import detect_internal_transfers
from db.models import (
    Account,
    AccountProviderMapping,
    AccountStatus,
    AgentRun,
    AgentRunError,
    AgentRunStatus,
    ExternalTransaction,
    PatrimonyDraftItem,
    PatrimonySnapshot,
    Transaction,
    TransactionType,
)


@dataclass(frozen=True)
class SnapshotImportResult:
    run_id: int
    status: AgentRunStatus
    accounts_seen: int
    balances_upserted: int
    transactions_created: int
    transactions_skipped: int
    errors: int


def import_account_snapshot(
    db: Session,
    snapshot_path: Path,
    date_from: date | None = None,
    date_to: date | None = None,
) -> SnapshotImportResult:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    started_at = datetime.now()

    provider = _snapshot_provider(payload)
    snapshot_date = _parse_datetime(payload["snapshot_date"])
    accounts = payload.get("accounts", [])
    if not isinstance(accounts, list):
        raise ValueError("snapshot accounts must be a list")

    run = AgentRun(
        agent_name="account_collector",
        provider=provider,
        external_run_id=payload.get("run_id"),
        status=AgentRunStatus.success,
        date_from=date_from,
        date_to=date_to,
        started_at=started_at,
        finished_at=started_at,
        accounts_count=len(accounts),
        transactions_count=0,
        snapshot_path=str(snapshot_path),
    )
    db.add(run)
    db.flush()

    balances_upserted = 0
    transactions_created = 0
    transactions_skipped = 0
    new_transactions: list[Transaction] = []

    for error in payload.get("errors", []):
        _add_run_error(db, run, None, "snapshot_error", str(error))

    for account in accounts:
        provider_account_id = str(account.get("external_id", "")).strip()
        if not provider_account_id:
            _add_run_error(db, run, None, "missing_provider_account_id", "account missing external_id", account)
            continue

        if account.get("status") != "success":
            _add_run_error(
                db,
                run,
                provider_account_id,
                "account_collection_failed",
                account.get("error") or "account collection failed",
                account,
            )
            continue

        mapping = (
            db.query(AccountProviderMapping)
            .filter_by(provider=provider, provider_account_id=provider_account_id, active=True)
            .first()
        )
        if not mapping:
            _add_run_error(
                db,
                run,
                provider_account_id,
                "missing_account_mapping",
                f"no local account mapping for {provider}:{provider_account_id}",
                account,
            )
            continue

        mapping.external_name = account.get("account_name")
        mapping.external_type = account.get("account_type")
        mapping.currency = account.get("currency", "EUR")
        mapping.last_seen_at = snapshot_date

        target_month = _target_draft_month(db, _parse_date(account["balance_date"]))
        _upsert_patrimony_draft_balance(
            db=db,
            account_id=mapping.local_account_id,
            month=target_month,
            value=float(account["balance"]),
            note=f"Imported from {provider} run {payload.get('run_id')} into draft",
        )
        balances_upserted += 1

        for raw_tx in account.get("transactions", []):
            provider_tx_id = _provider_transaction_id(provider, provider_account_id, raw_tx)
            if (
                db.query(ExternalTransaction)
                .filter_by(provider=provider, provider_transaction_id=provider_tx_id)
                .first()
            ):
                transactions_skipped += 1
                continue

            amount_signed = float(raw_tx["amount"])
            if amount_signed == 0:
                transactions_skipped += 1
                continue

            raw_label = str(raw_tx["label"])
            label = normalize_label(raw_label)
            tx = Transaction(
                account_id=mapping.local_account_id,
                date=_parse_date(raw_tx["date"]),
                raw_label=raw_label,
                label=label,
                amount=abs(amount_signed),
                transaction_type=TransactionType.credit if amount_signed > 0 else TransactionType.debit,
                category_id=categorize(label, db),
                category_source="auto",
                import_hash=_import_hash(provider, provider_tx_id),
            )
            db.add(tx)
            db.flush()

            db.add(ExternalTransaction(
                provider=provider,
                provider_transaction_id=provider_tx_id,
                provider_account_id=provider_account_id,
                local_transaction_id=tx.id,
                raw_payload_json=json.dumps(raw_tx, ensure_ascii=False),
            ))
            new_transactions.append(tx)
            transactions_created += 1

    if new_transactions:
        detect_internal_transfers(db, new_transactions)

    errors = len(run.errors)
    if errors and (balances_upserted > 0 or transactions_created > 0):
        run.status = AgentRunStatus.partial
    elif errors:
        run.status = AgentRunStatus.failed
    else:
        run.status = AgentRunStatus.success

    run.transactions_count = transactions_created
    run.finished_at = datetime.now()
    db.commit()

    return SnapshotImportResult(
        run_id=run.id,
        status=run.status,
        accounts_seen=len(accounts),
        balances_upserted=balances_upserted,
        transactions_created=transactions_created,
        transactions_skipped=transactions_skipped,
        errors=errors,
    )


def _snapshot_provider(payload: dict[str, Any]) -> str:
    accounts = payload.get("accounts", [])
    if accounts and isinstance(accounts, list):
        strategy = accounts[0].get("collection_strategy")
        if isinstance(strategy, str) and strategy:
            return strategy
    return "unknown"


def _target_draft_month(db: Session, balance_date: date) -> str:
    latest_published = (
        db.query(PatrimonySnapshot.month)
        .order_by(PatrimonySnapshot.month.desc())
        .limit(1)
        .scalar()
    )
    balance_month = balance_date.strftime("%Y-%m")
    if latest_published is None:
        return balance_month
    next_month = _next_month(latest_published)
    return max(balance_month, next_month)


def _next_month(month: str) -> str:
    year, month_num = (int(part) for part in month.split("-"))
    if month_num == 12:
        return f"{year + 1}-01"
    return f"{year}-{month_num + 1:02d}"


def _ensure_patrimony_draft(db: Session, month: str) -> None:
    if db.query(PatrimonyDraftItem.id).filter_by(month=month).first():
        return

    previous_month = (
        db.query(PatrimonySnapshot.month)
        .filter(PatrimonySnapshot.month < month)
        .order_by(PatrimonySnapshot.month.desc())
        .limit(1)
        .scalar()
    )
    source_values = {}
    if previous_month:
        source_values = {
            snap.account_id: snap.value
            for snap in db.query(PatrimonySnapshot).filter_by(month=previous_month).all()
        }

    accounts = db.query(Account).filter(Account.status == AccountStatus.actif).all()
    for account in accounts:
        source_value = source_values.get(account.id)
        value = source_value if source_value is not None else account.initial_balance
        db.add(PatrimonyDraftItem(
            account_id=account.id,
            month=month,
            value=value,
            note="Prérempli depuis le mois précédent" if previous_month else "Prérempli depuis le solde initial",
            source_month=previous_month,
            source_value=source_value,
        ))
    db.flush()


def _upsert_patrimony_draft_balance(
    db: Session,
    account_id: int,
    month: str,
    value: float,
    note: str,
) -> None:
    _ensure_patrimony_draft(db, month)
    existing = db.query(PatrimonyDraftItem).filter_by(account_id=account_id, month=month).first()
    if existing:
        existing.value = value
        existing.note = note
    else:
        db.add(PatrimonyDraftItem(account_id=account_id, month=month, value=value, note=note))


def _add_run_error(
    db: Session,
    run: AgentRun,
    provider_account_id: str | None,
    code: str,
    message: str,
    raw_payload: Any | None = None,
) -> None:
    db.add(AgentRunError(
        run_id=run.id,
        provider_account_id=provider_account_id,
        code=code,
        message=message,
        raw_payload_json=json.dumps(raw_payload, ensure_ascii=False) if raw_payload is not None else None,
    ))
    db.flush()


def _provider_transaction_id(
    provider: str,
    provider_account_id: str,
    raw_tx: dict[str, Any],
) -> str:
    external_id = raw_tx.get("external_id")
    if isinstance(external_id, str) and external_id.strip():
        return external_id.strip()

    fallback = "|".join([
        provider,
        provider_account_id,
        str(raw_tx.get("date", "")),
        str(raw_tx.get("label", "")),
        f"{float(raw_tx.get('amount', 0)):.2f}",
    ])
    return hashlib.sha256(fallback.encode()).hexdigest()[:32]


def _import_hash(provider: str, provider_tx_id: str) -> str:
    return hashlib.sha256(f"{provider}|{provider_tx_id}".encode()).hexdigest()[:32]


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)
