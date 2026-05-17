import os
import uuid
import hashlib
import tempfile
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from db.database import get_db
from db.models import Transaction, Account, Category, CategoryGroup, TransactionType, ProjectionMode
from core.importer import import_transactions
from core.categorizer import normalize_label, categorize
from core.transfer_detector import redetect_all

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _serialize_tx(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "account_id": tx.account_id,
        "account_name": tx.account.name if tx.account else None,
        "bank": tx.account.bank if tx.account else None,
        "date": tx.date,
        "label": tx.label,
        "raw_label": tx.raw_label,
        "amount": tx.amount,
        "type": tx.transaction_type,
        "category_id": tx.category_id,
        "category_name": tx.category.name if tx.category else None,
        "category_color": tx.category.color if tx.category else None,
        "is_internal_transfer": tx.is_internal_transfer,
        "is_neutral": tx.is_neutral,
        "is_investment": tx.is_investment,
        "is_compte_pro": tx.is_compte_pro,
        "category_source": tx.category_source,
    }


@router.get("/")
def list_transactions(
    account_id: Optional[int] = None,
    month: Optional[str] = None,        # format YYYY-MM
    category_id: Optional[int] = None,
    uncategorized: bool = False,
    exclude_transfers: bool = True,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Transaction)
    if account_id:
        q = q.filter(Transaction.account_id == account_id)
    if month:
        q = q.filter(Transaction.date.like(f"{month}%"))
    if category_id:
        q = q.filter(Transaction.category_id == category_id)
    if uncategorized:
        q = q.filter(
            Transaction.category_id == None,  # noqa: E711
            Transaction.is_internal_transfer == False,  # noqa: E712
            Transaction.is_neutral == False,  # noqa: E712
        )
    if exclude_transfers:
        q = q.filter(Transaction.is_internal_transfer == False)  # noqa: E712
    q = q.order_by(Transaction.date.desc())
    total = q.count()
    txs = q.offset(offset).limit(limit).all()
    return {"total": total, "items": [_serialize_tx(tx) for tx in txs]}


@router.post("/detect-transfers")
def run_transfer_detection(db: Session = Depends(get_db)):
    """Re-détecte tous les virements internes (noms membres + contrepartie montant)."""
    count = redetect_all(db)
    return {"detected": count}


@router.patch("/{tx_id}/transfer")
def toggle_transfer(tx_id: int, db: Session = Depends(get_db)):
    """Bascule manuellement is_internal_transfer d'une transaction."""
    tx = db.query(Transaction).filter_by(id=tx_id).first()
    if not tx:
        raise HTTPException(404, "Transaction introuvable")
    tx.is_internal_transfer = not tx.is_internal_transfer
    db.commit()
    return {"id": tx_id, "is_internal_transfer": tx.is_internal_transfer}


@router.patch("/{tx_id}/compte-pro")
def toggle_compte_pro(tx_id: int, db: Session = Depends(get_db)):
    """Bascule le flag apport compte pro — exclu des virements internes, déduit des revenus."""
    tx = db.query(Transaction).filter_by(id=tx_id).first()
    if not tx:
        raise HTTPException(404, "Transaction introuvable")
    tx.is_compte_pro = not tx.is_compte_pro
    if tx.is_compte_pro:
        tx.is_internal_transfer = False
        tx.is_neutral = False
        tx.is_investment = False
    db.commit()
    return {"id": tx_id, "is_compte_pro": tx.is_compte_pro}


@router.patch("/{tx_id}/investment")
def toggle_investment(tx_id: int, db: Session = Depends(get_db)):
    """Bascule le flag investissement — exclu des dépenses, compté séparément."""
    tx = db.query(Transaction).filter_by(id=tx_id).first()
    if not tx:
        raise HTTPException(404, "Transaction introuvable")
    tx.is_investment = not tx.is_investment
    if tx.is_investment:
        tx.is_internal_transfer = False
        tx.is_neutral = False
    db.commit()
    return {"id": tx_id, "is_investment": tx.is_investment}


@router.patch("/{tx_id}/neutral")
def toggle_neutral(tx_id: int, db: Session = Depends(get_db)):
    """Bascule le flag flux neutre (créance, prêt remboursé...) — exclu de tous les calculs."""
    tx = db.query(Transaction).filter_by(id=tx_id).first()
    if not tx:
        raise HTTPException(404, "Transaction introuvable")
    tx.is_neutral = not tx.is_neutral
    # Si on marque neutre, on retire le flag interne si présent
    if tx.is_neutral:
        tx.is_internal_transfer = False
    db.commit()
    return {"id": tx_id, "is_neutral": tx.is_neutral}


class ForceCreateBody(BaseModel):
    account_id: int
    date: str          # YYYY-MM-DD
    raw_label: str
    amount: float
    type: str          # "debit" | "credit"


@router.post("/force-create")
def force_create_transaction(body: ForceCreateBody, db: Session = Depends(get_db)):
    """Crée une transaction en ignorant le contrôle doublon (pour les faux doublons)."""
    account = db.query(Account).filter_by(id=body.account_id).first()
    if not account:
        raise HTTPException(404, "Compte introuvable")

    tx_date = date.fromisoformat(body.date)
    tx_type = TransactionType.debit if body.type == "debit" else TransactionType.credit

    # Hash avec sel aléatoire pour éviter toute collision
    salt = uuid.uuid4().hex[:8]
    import_hash = hashlib.sha256(
        f"{body.account_id}|{tx_date}|{body.raw_label}|{body.amount:.2f}|{salt}".encode()
    ).hexdigest()[:32]

    label = normalize_label(body.raw_label)
    category_id = categorize(label, db)

    tx = Transaction(
        account_id=body.account_id,
        date=tx_date,
        raw_label=body.raw_label,
        label=label,
        amount=body.amount,
        transaction_type=tx_type,
        category_id=category_id,
        category_source="auto" if category_id else None,
        import_hash=import_hash,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return _serialize_tx(tx)


@router.post("/import")
async def upload_and_import(
    account_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload un relevé CSV/Excel et l'importe pour le compte donné."""
    account = db.query(Account).filter_by(id=account_id).first()
    if not account:
        raise HTTPException(404, "Compte introuvable")

    # Sauvegarde temporaire
    fname = file.filename or ""
    if fname.endswith(".xlsx"):
        suffix = ".xlsx"
    elif fname.endswith(".xls"):
        suffix = ".xls"
    else:
        suffix = ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = import_transactions(db, account_id, tmp_path)
    finally:
        os.unlink(tmp_path)

    if "error" in result:
        raise HTTPException(422, detail=result)

    return {"account": account.name, **result}


@router.get("/summary/monthly")
def monthly_summary(
    month: str,  # YYYY-MM
    db: Session = Depends(get_db),
):
    """Agrégats budget pour un mois donné."""
    txs = (
        db.query(Transaction)
        .filter(
            Transaction.date.like(f"{month}%"),
            Transaction.is_internal_transfer == False,  # noqa: E712
            Transaction.is_neutral == False,            # noqa: E712
        )
        .all()
    )

    # Catégories considérées comme "revenus réels" (les autres crédits = remboursements)
    INCOME_CATS = {"Revenus"}

    # Séparer : vrais revenus vs remboursements
    real_revenue_txs = [
        t for t in txs
        if t.transaction_type == TransactionType.credit
        and (t.category is None or t.category.name in INCOME_CATS)
    ]
    refund_txs = [
        t for t in txs
        if t.transaction_type == TransactionType.credit
        and t.category is not None
        and t.category.name not in INCOME_CATS
    ]
    all_debit_txs = [t for t in txs if t.transaction_type == TransactionType.debit]

    # Séparer investissements et compte pro des vraies dépenses
    invest_txs = [t for t in all_debit_txs if t.is_investment]
    debit_txs  = [t for t in all_debit_txs if not t.is_investment and not t.is_compte_pro]
    investissements = round(sum(t.amount for t in invest_txs), 2)

    revenus_bruts = sum(t.amount for t in real_revenue_txs)
    refunds_total = sum(t.amount for t in refund_txs)
    depenses      = max(sum(t.amount for t in debit_txs) - refunds_total, 0)

    # Apports compte pro (flag is_compte_pro) = déduction des revenus
    apports_pro = sum(
        t.amount for t in
        db.query(Transaction).filter(
            Transaction.date.like(f"{month}%"),
            Transaction.is_compte_pro == True,  # noqa: E712
            Transaction.transaction_type == TransactionType.debit,
        ).all()
    )

    revenus = max(revenus_bruts - apports_pro, 0)
    epargne = revenus - depenses
    taux    = round((epargne / revenus * 100), 1) if revenus else 0

    # Par catégorie (détaillé) — débits moins remboursements de la même catégorie
    by_cat: dict[str, dict] = {}
    for tx in debit_txs:
        name  = tx.category.name if tx.category else "Autre"
        color = tx.category.color if tx.category else "#6b7280"
        if name not in by_cat:
            by_cat[name] = {"name": name, "color": color, "total": 0}
        by_cat[name]["total"] += tx.amount
    for tx in refund_txs:
        name  = tx.category.name
        color = tx.category.color
        if name in by_cat:
            by_cat[name]["total"] -= tx.amount
        else:
            by_cat[name] = {"name": name, "color": color, "total": -tx.amount}

    categories = sorted(
        [c for c in by_cat.values() if c["total"] > 0],
        key=lambda x: x["total"], reverse=True
    )

    # Par groupe avec détail catégories (vue simplifiée + drill-down)
    by_group: dict[str, dict] = {}
    def _add_to_group(tx: Transaction, sign: float):
        if tx.category and tx.category.group:
            gname  = tx.category.group.name
            gcolor = tx.category.group.color
        else:
            gname  = "Autre"
            gcolor = "#6b7280"
        cname  = tx.category.name  if tx.category else "Autre"
        ccolor = tx.category.color if tx.category else "#6b7280"
        if gname not in by_group:
            by_group[gname] = {"name": gname, "color": gcolor, "total": 0, "categories": {}}
        by_group[gname]["total"] += sign * tx.amount
        cats = by_group[gname]["categories"]
        if cname not in cats:
            cats[cname] = {"name": cname, "color": ccolor, "total": 0}
        cats[cname]["total"] += sign * tx.amount

    for tx in debit_txs:
        _add_to_group(tx, +1)
    for tx in refund_txs:
        _add_to_group(tx, -1)

    # Supprimer groupes/catégories avec total <= 0
    for g in by_group.values():
        g["categories"] = {k: v for k, v in g["categories"].items() if v["total"] > 0}
    by_group = {k: v for k, v in by_group.items() if v["total"] > 0}

    # Récupérer budget annuel par groupe
    db_groups_meta = {gr.name: gr for gr in db.query(CategoryGroup).all()}
    pace = _pace_data(month)
    for gr in db_groups_meta.values():
        if gr.budget_annual and gr.name not in by_group:
            by_group[gr.name] = {
                "name": gr.name,
                "color": gr.color,
                "total": 0,
                "categories": {},
            }

    groups = sorted(
        [
            _group_with_budget_projection(g, db_groups_meta.get(g["name"]), month, pace, db)
            for g in by_group.values()
        ],
        key=lambda x: x["total"],
        reverse=True,
    )

    # Virements internes (les deux sens)
    internal_all = (
        db.query(Transaction)
        .filter(
            Transaction.date.like(f"{month}%"),
            Transaction.is_internal_transfer == True,  # noqa: E712
            Transaction.is_neutral == False,           # noqa: E712
            Transaction.is_compte_pro == False,        # noqa: E712
        )
        .all()
    )
    internal_envoyes = sum(t.amount for t in internal_all if t.transaction_type == TransactionType.debit)
    internal_recus   = sum(t.amount for t in internal_all if t.transaction_type == TransactionType.credit)
    total_internal   = internal_envoyes  # rétro-compat

    # Top 10 dépenses
    top_expenses = sorted(
        [t for t in txs if t.transaction_type == TransactionType.debit],
        key=lambda t: t.amount,
        reverse=True,
    )[:10]
    top10 = [
        {
            "label": tx.label,
            "amount": round(tx.amount, 2),
            "category": tx.category.name if tx.category else "Autre",
            "category_color": tx.category.color if tx.category else "#6b7280",
        }
        for tx in top_expenses
    ]

    return {
        "month": month,
        "revenus": round(revenus, 2),
        "revenus_bruts": round(revenus_bruts, 2),
        "apports_pro": round(apports_pro, 2),
        "depenses": round(depenses, 2),
        "investissements": investissements,
        "epargne": round(epargne, 2),
        "taux_epargne": taux,
        "categories": categories,
        "groups": groups,
        "virements_internes": round(total_internal, 2),
        "virements_envoyes": round(internal_envoyes, 2),
        "virements_recus": round(internal_recus, 2),
        "nb_transactions": len(txs),
        "top10": top10,
        **pace,
    }


def _group_with_budget_projection(
    g: dict,
    meta: CategoryGroup | None,
    month: str,
    pace: dict,
    db: Session,
) -> dict:
    budget_annual = meta.budget_annual if meta else None
    budget_monthly = round(budget_annual / 12, 2) if budget_annual else None
    total = round(g["total"], 2)
    mode = meta.projection_mode if meta else ProjectionMode.linear
    if not isinstance(mode, ProjectionMode):
        try:
            mode = ProjectionMode(mode or ProjectionMode.linear)
        except ValueError:
            mode = ProjectionMode.linear

    projection_amount = total
    projection_source = "actual"
    projection_reference: float | None = None

    if pace["is_current_month"]:
        if mode == ProjectionMode.linear:
            factor = pace["pace_factor"] or 1
            projection_amount = round(total * factor, 2)
            projection_source = "pace"
            projection_reference = factor
        elif mode == ProjectionMode.fixed_historical:
            if total > 0:
                projection_amount = total
                projection_source = "actual_paid"
            else:
                projection_amount = _historical_group_average(db, meta.id if meta else None, month, months=6)
                projection_source = "historical_6m"
            projection_reference = projection_amount
        else:
            projection_amount = total
            projection_source = "actual_only"

    return {
        **g,
        "total": total,
        "categories": sorted(g["categories"].values(), key=lambda x: x["total"], reverse=True),
        "budget_annual": budget_annual,
        "budget_monthly": budget_monthly,
        "over_limit": bool(budget_monthly and total > budget_monthly),
        "projection_mode": mode.value,
        "projection_amount": round(projection_amount, 2),
        "projection_over_limit": bool(budget_monthly and projection_amount > budget_monthly),
        "projection_source": projection_source,
        "projection_reference": projection_reference,
    }


def _historical_group_average(db: Session, group_id: int | None, month: str, months: int = 6) -> float:
    if group_id is None:
        return 0.0

    month_start = datetime.strptime(f"{month}-01", "%Y-%m-%d").date()
    start_date = month_start - relativedelta(months=months)
    rows = (
        db.query(Transaction)
        .join(Category, Transaction.category_id == Category.id)
        .filter(
            Category.group_id == group_id,
            Transaction.date >= start_date,
            Transaction.date < month_start,
            Transaction.is_internal_transfer == False,  # noqa: E712
            Transaction.is_neutral == False,            # noqa: E712
        )
        .all()
    )

    totals: dict[str, float] = {}
    for tx in rows:
        key = tx.date.strftime("%Y-%m")
        totals.setdefault(key, 0.0)
        if tx.transaction_type == TransactionType.debit and not tx.is_investment and not tx.is_compte_pro:
            totals[key] += tx.amount
        elif (
            tx.transaction_type == TransactionType.credit
            and tx.category is not None
            and tx.category.name != "Revenus"
        ):
            totals[key] -= tx.amount

    return round(sum(max(v, 0.0) for v in totals.values()) / months, 2)


def _pace_data(month: str) -> dict:
    """Retourne les données de pace si le mois est le mois en cours."""
    from calendar import monthrange
    today = date.today()
    current_month = today.strftime("%Y-%m")
    if month != current_month:
        return {"is_current_month": False, "days_elapsed": None, "days_in_month": None, "pace_factor": None}
    days_in_month = monthrange(today.year, today.month)[1]
    days_elapsed  = today.day
    pace_factor   = round(days_in_month / days_elapsed, 4) if days_elapsed > 0 else None
    return {
        "is_current_month": True,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "pace_factor": pace_factor,
    }


@router.get("/summary/history")
def monthly_history(
    months: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
):
    """Retourne l'agrégat budget des N derniers mois (pour graphique évolution)."""
    today = date.today().replace(day=1)
    result = []

    for i in range(months - 1, -1, -1):
        ref = today - relativedelta(months=i)
        month_str = ref.strftime("%Y-%m")
        short = ref.strftime("%b %Y")

        txs = (
            db.query(Transaction)
            .filter(
                Transaction.date.like(f"{month_str}%"),
                Transaction.is_internal_transfer == False,  # noqa: E712
            )
            .all()
        )
        revenus  = sum(t.amount for t in txs if t.transaction_type == TransactionType.credit)
        depenses = sum(t.amount for t in txs if t.transaction_type == TransactionType.debit)
        epargne  = revenus - depenses

        result.append({
            "month": month_str,
            "label": short,
            "revenus": round(revenus, 2),
            "depenses": round(depenses, 2),
            "epargne": round(epargne, 2),
        })

    return result


@router.get("/summary/rolling")
def rolling_summary(
    months: int = Query(12, ge=3, le=24),
    pivot_month: Optional[str] = None,   # YYYY-MM, défaut = dernier mois complet
    db: Session = Depends(get_db),
):
    """
    Suivi annuel glissant par groupe de catégories.
    pivot_month : mois de fin de la fenêtre (inclus). Si absent ou mois en cours → mois précédent.
    """
    from sqlalchemy import func as sqlfunc
    from calendar import monthrange

    today = date.today()
    current_month_str = today.strftime("%Y-%m")

    # Déterminer le mois pivot (dernier mois de la fenêtre, complet)
    if pivot_month and pivot_month != current_month_str:
        y, m = int(pivot_month.split("-")[0]), int(pivot_month.split("-")[1])
        pivot = date(y, m, 1)
    else:
        # Pas de pivot ou mois en cours → dernier mois complet
        pivot = today.replace(day=1) - relativedelta(days=1)
        pivot = pivot.replace(day=1)

    # end = dernier jour du mois pivot, start = N mois avant
    last_day = monthrange(pivot.year, pivot.month)[1]
    end   = date(pivot.year, pivot.month, last_day)
    start = pivot - relativedelta(months=months - 1)

    # Récupérer tous les groupes avec leur budget
    db_groups = (
        db.query(CategoryGroup)
        .order_by(CategoryGroup.sort_order, CategoryGroup.name)
        .all()
    )

    # Dépenses par groupe sur la période (hors investissements)
    rows = (
        db.query(
            CategoryGroup.id,
            sqlfunc.sum(Transaction.amount).label("total"),
        )
        .join(Category, Category.group_id == CategoryGroup.id)
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.transaction_type == TransactionType.debit,
            Transaction.is_internal_transfer == False,  # noqa: E712
            Transaction.is_investment == False,          # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by(CategoryGroup.id)
        .all()
    )
    totals_by_group = {r.id: float(r.total or 0) for r in rows}

    # Dépenses par groupe × mois (pour le graphe évolution)
    monthly_rows = (
        db.query(
            CategoryGroup.id,
            CategoryGroup.name,
            sqlfunc.strftime("%Y-%m", Transaction.date).label("month"),
            sqlfunc.sum(Transaction.amount).label("total"),
        )
        .join(Category, Category.group_id == CategoryGroup.id)
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.transaction_type == TransactionType.debit,
            Transaction.is_internal_transfer == False,  # noqa: E712
            Transaction.is_investment == False,          # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by(CategoryGroup.id, CategoryGroup.name, "month")
        .all()
    )

    # Index : group_id → {month → total}
    monthly_by_group: dict[int, dict[str, float]] = {}
    for r in monthly_rows:
        monthly_by_group.setdefault(r.id, {})[r.month] = float(r.total or 0)

    # Construire la liste des mois de la fenêtre (du plus ancien au plus récent)
    month_labels = []
    for i in range(months - 1, -1, -1):
        m = pivot - relativedelta(months=i)
        month_labels.append(m.strftime("%Y-%m"))

    result_groups = []
    for gr in db_groups:
        total_period = totals_by_group.get(gr.id, 0.0)
        if total_period == 0 and gr.budget_annual is None:
            continue  # groupe sans données ni budget → skip

        monthly_avg = round(total_period / months, 2)
        budget_annual = gr.budget_annual
        budget_monthly = round(budget_annual / 12, 2) if budget_annual else None
        pace_ratio = round(total_period / budget_annual, 3) if budget_annual else None
        over_annual = bool(budget_annual and total_period > budget_annual)

        # Projection : à ce rythme, total annuel = monthly_avg * 12
        projected_annual = round(monthly_avg * 12, 2)

        months_data = [
            {"month": m, "total": round(monthly_by_group.get(gr.id, {}).get(m, 0.0), 2)}
            for m in month_labels
        ]

        result_groups.append({
            "id": gr.id,
            "name": gr.name,
            "color": gr.color,
            "total_period": round(total_period, 2),
            "monthly_avg": monthly_avg,
            "projected_annual": projected_annual,
            "budget_annual": budget_annual,
            "budget_monthly": budget_monthly,
            "pace_ratio": pace_ratio,
            "over_annual": over_annual,
            "months_data": months_data,
        })

    # Trier par total décroissant
    result_groups.sort(key=lambda x: x["total_period"], reverse=True)

    return {
        "window_months": months,
        "start": str(start),
        "end": str(end),
        "groups": result_groups,
    }
