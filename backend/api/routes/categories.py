from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from typing import Optional
from db.database import get_db
from db.models import Category, CategoryRule, Transaction, RuleMatchType, RuleSource
from core.categorizer import categorize

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryOut(BaseModel):
    id: int
    name: str
    color: str
    icon: Optional[str]
    is_system: bool
    model_config = {"from_attributes": True}


class AssignCategory(BaseModel):
    transaction_id: int
    category_id: int
    save_rule: bool = True   # True = règle + rétroactivité, False = juste cette transaction


class CreateCategory(BaseModel):
    name: str
    color: str = "#6b7280"


@router.get("/")
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.name).all()


@router.post("/")
def create_category(body: CreateCategory, db: Session = Depends(get_db)):
    """Crée une nouvelle catégorie utilisateur."""
    existing = db.query(Category).filter(Category.name.ilike(body.name)).first()
    if existing:
        raise HTTPException(400, f"Catégorie '{body.name}' existe déjà")
    cat = Category(name=body.name.strip(), color=body.color, is_system=False)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.post("/assign")
def assign_category(body: AssignCategory, db: Session = Depends(get_db)):
    """Corrige la catégorie d'une transaction et mémorise la règle."""
    tx = db.query(Transaction).filter_by(id=body.transaction_id).first()
    if not tx:
        raise HTTPException(404, "Transaction introuvable")

    cat = db.query(Category).filter_by(id=body.category_id).first()
    if not cat:
        raise HTTPException(404, "Catégorie introuvable")

    is_transfer_cat = cat.name in ("Investissement", "Virement interne", "Épargne", "Compte pro")

    # Mise à jour de la transaction — toujours "manual" (choix explicite de l'utilisateur)
    tx.category_id = body.category_id
    tx.category_source = "manual"
    if is_transfer_cat:
        tx.is_internal_transfer = True
    db.commit()

    updated_count = 0
    if body.save_rule and tx.label:
        pattern = tx.label.lower()[:40]
        existing = (
            db.query(CategoryRule)
            .filter_by(pattern=pattern, source=RuleSource.user)
            .first()
        )
        if existing:
            existing.category_id = body.category_id
        else:
            db.add(CategoryRule(
                pattern=pattern,
                match_type=RuleMatchType.contains,
                category_id=body.category_id,
                priority=100,
                source=RuleSource.user,
            ))
        db.flush()

        # Rétroactivité : uniquement les transactions NON manuellement overridées
        # (NULL category_source = jamais touché = éligible)
        from sqlalchemy import or_
        similar = (
            db.query(Transaction)
            .filter(
                Transaction.label.ilike(f"%{pattern}%"),
                Transaction.id != tx.id,
                or_(
                    Transaction.category_source == None,   # noqa: E711
                    Transaction.category_source == "auto",
                ),
            )
            .all()
        )
        for t in similar:
            t.category_id = body.category_id
            t.category_source = "auto"
            if is_transfer_cat:
                t.is_internal_transfer = True
        updated_count = len(similar)

    db.commit()
    return {"ok": True, "transaction_id": tx.id, "category": cat.name, "retroactive_count": updated_count}


@router.get("/preview-assign")
def preview_assign(
    transaction_id: int = Query(...),
    category_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Retourne les transactions qui seraient affectées par une règle de catégorisation."""
    tx = db.query(Transaction).filter_by(id=transaction_id).first()
    if not tx:
        raise HTTPException(404, "Transaction introuvable")

    pattern = tx.label.lower()[:40]
    similar = (
        db.query(Transaction)
        .filter(
            Transaction.label.ilike(f"%{pattern}%"),
            Transaction.id != transaction_id,
            or_(
                Transaction.category_source == None,   # noqa: E711
                Transaction.category_source == "auto",
            ),
        )
        .order_by(Transaction.date.desc())
        .all()
    )

    return {
        "pattern": pattern,
        "count": len(similar),
        "transactions": [
            {
                "id": t.id,
                "date": str(t.date),
                "label": t.label,
                "amount": t.amount,
                "type": t.transaction_type,
                "bank": t.account.bank if t.account else None,
                "account_name": t.account.name if t.account else None,
                "category_id": t.category_id,
                "category_name": t.category.name if t.category else None,
                "category_color": t.category.color if t.category else None,
                "category_source": t.category_source,
            }
            for t in similar[:30]
        ],
    }


@router.post("/recategorize-all")
def recategorize_all(db: Session = Depends(get_db)):
    """Re-applique toutes les règles sur les transactions non catégorisées manuellement."""
    txs = (
        db.query(Transaction)
        .filter(
            or_(
                Transaction.category_source == None,   # noqa: E711
                Transaction.category_source == "auto",
            )
        )
        .all()
    )

    updated = 0
    for tx in txs:
        new_cat = categorize(tx.label, db)
        if new_cat != tx.category_id:
            tx.category_id = new_cat
            tx.category_source = "auto" if new_cat else None
            updated += 1

    db.commit()
    return {"updated": updated, "total": len(txs)}
