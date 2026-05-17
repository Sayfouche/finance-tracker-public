from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from db.models import ExternalTransaction, Transaction


@dataclass(frozen=True)
class DuplicateCandidate:
    provider_transaction_id: str
    provider_transaction_local_id: int
    existing_transaction_id: int
    account_name: str
    date: date
    amount: float
    transaction_type: str
    provider_label: str
    existing_label: str


@dataclass(frozen=True)
class ReconcileResult:
    candidates: list[DuplicateCandidate]
    applied: bool


def find_provider_duplicates(
    db: Session,
    provider: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[DuplicateCandidate]:
    external_rows = db.query(ExternalTransaction).filter_by(provider=provider).all()
    external_tx_ids = {row.local_transaction_id for row in external_rows}
    candidates: list[DuplicateCandidate] = []

    for external in external_rows:
        provider_tx = db.get(Transaction, external.local_transaction_id)
        if provider_tx is None:
            continue
        if date_from and provider_tx.date < date_from:
            continue
        if date_to and provider_tx.date > date_to:
            continue

        matches = (
            db.query(Transaction)
            .filter(
                Transaction.id.notin_(external_tx_ids),
                Transaction.account_id == provider_tx.account_id,
                Transaction.date == provider_tx.date,
                Transaction.amount == provider_tx.amount,
                Transaction.transaction_type == provider_tx.transaction_type,
            )
            .all()
        )
        if len(matches) != 1:
            continue

        existing_tx = matches[0]
        candidates.append(DuplicateCandidate(
            provider_transaction_id=external.provider_transaction_id,
            provider_transaction_local_id=provider_tx.id,
            existing_transaction_id=existing_tx.id,
            account_name=provider_tx.account.name if provider_tx.account else "",
            date=provider_tx.date,
            amount=provider_tx.amount,
            transaction_type=provider_tx.transaction_type.value,
            provider_label=provider_tx.label,
            existing_label=existing_tx.label,
        ))

    return candidates


def reconcile_provider_duplicates(
    db: Session,
    provider: str,
    date_from: date | None = None,
    date_to: date | None = None,
    apply: bool = False,
) -> ReconcileResult:
    candidates = find_provider_duplicates(db, provider, date_from, date_to)

    if apply:
        for candidate in candidates:
            external = (
                db.query(ExternalTransaction)
                .filter_by(
                    provider=provider,
                    provider_transaction_id=candidate.provider_transaction_id,
                )
                .one()
            )
            provider_tx = db.get(Transaction, candidate.provider_transaction_local_id)
            external.local_transaction_id = candidate.existing_transaction_id
            if provider_tx is not None:
                db.delete(provider_tx)
        db.commit()

    return ReconcileResult(candidates=candidates, applied=apply)
