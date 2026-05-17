"""
Détection des virements internes entre comptes du même foyer.
Deux stratégies :
1. Montant opposé sur un autre compte à ±3 jours
2. Libellé contenant le nom d'un membre du foyer + "virement"
"""
from datetime import timedelta
from sqlalchemy.orm import Session
from db.models import Transaction, TransactionType, FamilyMember


def detect_internal_transfers(db: Session, new_transactions: list[Transaction]) -> int:
    """
    Pour chaque nouvelle transaction, cherche une contrepartie dans la base
    ou détecte un virement par nom de membre du foyer.
    Retourne le nombre de transactions marquées.
    """
    # Noms des membres du foyer (en minuscules)
    member_names = [
        m.first_name.lower()
        for m in db.query(FamilyMember).all()
    ]

    detected = 0

    for tx in new_transactions:
        if tx.is_internal_transfer:
            continue

        # Stratégie 1 : contrepartie montant opposé sur autre compte
        window_start = tx.date - timedelta(days=3)
        window_end   = tx.date + timedelta(days=3)
        opposite_type = (
            TransactionType.credit if tx.transaction_type == TransactionType.debit
            else TransactionType.debit
        )
        candidate = (
            db.query(Transaction)
            .filter(
                Transaction.id != tx.id,
                Transaction.amount == tx.amount,
                Transaction.transaction_type == opposite_type,
                Transaction.date >= window_start,
                Transaction.date <= window_end,
                Transaction.is_internal_transfer == False,  # noqa: E712
                Transaction.account_id != tx.account_id,
            )
            .first()
        )
        if candidate:
            tx.is_internal_transfer = True
            tx.transfer_pair_id = candidate.id
            candidate.is_internal_transfer = True
            candidate.transfer_pair_id = tx.id
            detected += 1
            continue

        # Stratégie 2 : libellé contient "virement" + nom d'un membre
        label_lower = tx.label.lower()
        if "virement" in label_lower:
            if any(name in label_lower for name in member_names):
                tx.is_internal_transfer = True
                detected += 1

    db.commit()
    return detected


def redetect_all(db: Session) -> int:
    """Re-passe toutes les transactions non marquées pour détecter les virements internes."""
    all_txs = (
        db.query(Transaction)
        .filter(Transaction.is_internal_transfer == False)  # noqa: E712
        .all()
    )
    return detect_internal_transfers(db, all_txs)
