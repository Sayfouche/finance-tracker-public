from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from dateutil.relativedelta import relativedelta
from db.database import get_db
from db.models import CategoryGroup, Category, Transaction, TransactionType, ProjectionMode

router = APIRouter(prefix="/category-groups", tags=["category-groups"])


class GroupOut(BaseModel):
    id: int
    name: str
    color: str
    sort_order: int
    model_config = {"from_attributes": True}


class GroupCreate(BaseModel):
    name: str
    color: str = "#6b7280"
    sort_order: int = 99
    budget_annual: Optional[float] = None
    exclude_from_budget: bool = False
    projection_mode: ProjectionMode = ProjectionMode.linear


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    budget_annual: Optional[float] = None   # 0 = supprimer le budget
    exclude_from_budget: Optional[bool] = None
    projection_mode: Optional[ProjectionMode] = None


def _serialize_group(g: CategoryGroup) -> dict:
    return {
        "id": g.id,
        "name": g.name,
        "color": g.color,
        "sort_order": g.sort_order,
        "budget_annual": g.budget_annual,
        "budget_monthly": round(g.budget_annual / 12, 2) if g.budget_annual else None,
        "exclude_from_budget": bool(g.exclude_from_budget),
        "projection_mode": g.projection_mode.value if hasattr(g.projection_mode, "value") else g.projection_mode,
        "categories": [
            {"id": c.id, "name": c.name, "color": c.color}
            for c in sorted(g.categories, key=lambda x: x.name)
        ],
    }


@router.get("/")
def list_groups(db: Session = Depends(get_db)):
    groups = db.query(CategoryGroup).order_by(CategoryGroup.sort_order, CategoryGroup.name).all()
    return [_serialize_group(g) for g in groups]


@router.post("/")
def create_group(body: GroupCreate, db: Session = Depends(get_db)):
    existing = db.query(CategoryGroup).filter_by(name=body.name).first()
    if existing:
        raise HTTPException(400, f"Groupe '{body.name}' existe déjà")
    g = CategoryGroup(name=body.name.strip(), color=body.color, sort_order=body.sort_order,
                      budget_annual=body.budget_annual,
                      exclude_from_budget=body.exclude_from_budget,
                      projection_mode=body.projection_mode)
    db.add(g)
    db.commit()
    db.refresh(g)
    return _serialize_group(g)


@router.patch("/{group_id}")
def update_group(group_id: int, body: GroupUpdate, db: Session = Depends(get_db)):
    g = db.query(CategoryGroup).filter_by(id=group_id).first()
    if not g:
        raise HTTPException(404, "Groupe introuvable")
    if body.name is not None:
        g.name = body.name.strip()
    if body.color is not None:
        g.color = body.color
    if body.sort_order is not None:
        g.sort_order = body.sort_order
    if body.budget_annual is not None:
        g.budget_annual = None if body.budget_annual == 0 else body.budget_annual
    if body.exclude_from_budget is not None:
        g.exclude_from_budget = body.exclude_from_budget
    if body.projection_mode is not None:
        g.projection_mode = body.projection_mode
    db.commit()
    db.refresh(g)
    return _serialize_group(g)


@router.delete("/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    g = db.query(CategoryGroup).filter_by(id=group_id).first()
    if not g:
        raise HTTPException(404, "Groupe introuvable")
    for cat in g.categories:
        cat.group_id = None
    db.delete(g)
    db.commit()
    return {"ok": True}


@router.patch("/{group_id}/assign-category/{category_id}")
def assign_category_to_group(group_id: int, category_id: int, db: Session = Depends(get_db)):
    g = db.query(CategoryGroup).filter_by(id=group_id).first()
    if not g:
        raise HTTPException(404, "Groupe introuvable")
    cat = db.query(Category).filter_by(id=category_id).first()
    if not cat:
        raise HTTPException(404, "Catégorie introuvable")
    cat.group_id = group_id
    db.commit()
    return {"ok": True, "category": cat.name, "group": g.name}


@router.patch("/unassign-category/{category_id}")
def unassign_category(category_id: int, db: Session = Depends(get_db)):
    cat = db.query(Category).filter_by(id=category_id).first()
    if not cat:
        raise HTTPException(404, "Catégorie introuvable")
    cat.group_id = None
    db.commit()
    return {"ok": True}


# ─── Budget distribution ──────────────────────────────────────────────────────

class BudgetDistributeBody(BaseModel):
    total_monthly_budget: float   # budget mensuel global (ex: 5000)
    months_history: int = 3
    apply: bool = False


class DistributionItem(BaseModel):
    group_id: int
    group_name: str
    group_color: str
    avg_monthly: float
    suggested_annual: float      # budget annuel suggéré pour ce groupe
    suggested_monthly: float     # = suggested_annual / 12
    proportion_pct: float


@router.post("/distribute-budget", response_model=List[DistributionItem])
def distribute_budget(body: BudgetDistributeBody, db: Session = Depends(get_db)):
    """
    Calcule une répartition de budget annuel par groupe basée sur les moyennes historiques.
    Input: budget mensuel global → output: budget annuel par groupe.
    """
    if body.months_history < 1:
        raise HTTPException(400, "months_history doit être >= 1")
    if body.total_monthly_budget <= 0:
        raise HTTPException(400, "total_monthly_budget doit être > 0")

    today = date.today()
    start_date = today - relativedelta(months=body.months_history)

    rows = (
        db.query(
            CategoryGroup.id,
            CategoryGroup.name,
            CategoryGroup.color,
            func.sum(Transaction.amount).label("total_spent"),
        )
        .join(Category, Category.group_id == CategoryGroup.id)
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.transaction_type == TransactionType.debit,
            Transaction.is_internal_transfer == False,  # noqa: E712
            Transaction.date >= start_date,
            Transaction.date <= today,
        )
        .group_by(CategoryGroup.id, CategoryGroup.name, CategoryGroup.color)
        .all()
    )

    group_avgs: List[dict] = []
    for row in rows:
        avg = (row.total_spent or 0.0) / body.months_history
        if avg > 0:
            group_avgs.append({
                "group_id": row.id,
                "group_name": row.name,
                "group_color": row.color,
                "avg_monthly": round(avg, 2),
            })

    if not group_avgs:
        return []

    total_avg = sum(g["avg_monthly"] for g in group_avgs)

    result: List[DistributionItem] = []
    for g in group_avgs:
        proportion = g["avg_monthly"] / total_avg
        monthly_limit = proportion * body.total_monthly_budget
        # Arrondi au 10€ le plus proche
        suggested_monthly = round(monthly_limit / 10) * 10
        suggested_annual  = suggested_monthly * 12
        proportion_pct = round(proportion * 100, 1)

        result.append(DistributionItem(
            group_id=g["group_id"],
            group_name=g["group_name"],
            group_color=g["group_color"],
            avg_monthly=g["avg_monthly"],
            suggested_annual=suggested_annual,
            suggested_monthly=suggested_monthly,
            proportion_pct=proportion_pct,
        ))

        if body.apply:
            grp = db.query(CategoryGroup).filter_by(id=g["group_id"]).first()
            if grp:
                grp.budget_annual = suggested_annual

    if body.apply:
        db.commit()

    return result
