from datetime import datetime
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import distinct
from pydantic import BaseModel
from typing import Optional
from db.database import get_db
from db.models import PatrimonyDraftItem, PatrimonySnapshot, Account, AccountStatus

TODAY = datetime.now().strftime("%Y-%m")

router = APIRouter(prefix="/patrimony", tags=["patrimony"])


ASSET_TYPE_GROUPS = {
    "immobilier":    ("Immobilier",        "#f97316"),
    "courant":       ("Comptes courants",  "#3b82f6"),
    "livret":        ("Livrets",           "#22c55e"),
    "epargne":       ("Épargne",           "#10b981"),
    "cto":           ("CTO",               "#8b5cf6"),
    "pea":           ("PEA",               "#7c3aed"),
    "per":           ("PER",               "#f59e0b"),
    "assurance_vie": ("Assurance-vie",     "#06b6d4"),
    "autre_actif":   ("Autres actifs",     "#6b7280"),
}

NET_SERIES = [
    ("immobilier_equity", "Immobilier (equity)", "#f97316"),
    ("courant", "Comptes courants", "#3b82f6"),
    ("livret", "Livrets", "#22c55e"),
    ("epargne", "Épargne", "#10b981"),
    ("cto", "CTO", "#8b5cf6"),
    ("pea", "PEA", "#7c3aed"),
    ("per", "PER", "#f59e0b"),
    ("assurance_vie", "Assurance-vie", "#06b6d4"),
    ("autre_actif", "Autres actifs", "#6b7280"),
]

LIQUIDITY_SERIES = [
    ("securite",   "Sécurité",      "#22c55e"),
    ("accessible", "Accessible",    "#06b6d4"),
    ("investi_lt", "Investi LT",    "#6366f1"),
    ("immo",       "Immo (equity)", "#f97316"),
]

METRICS_SERIES = [
    ("epargne_securite",     "Épargne sécurité", "#22c55e"),
    ("epargne_dispo",        "Épargne dispo",    "#06b6d4"),
    ("capital_investi",      "Capital investi",  "#6366f1"),
    ("investi_plus_livrets", "Investi + livrets","#8b5cf6"),
    ("patrimoine_hors_rp",   "Hors immo",        "#f59e0b"),
]


def _snap_total(snaps_map: dict) -> float:
    actifs  = sum(v for v in snaps_map.values() if v > 0)
    passifs = sum(abs(v) for v in snaps_map.values() if v < 0)
    return round(actifs - passifs, 2)


class SnapshotUpsert(BaseModel):
    account_id: int
    month: str        # YYYY-MM
    value: float
    note: Optional[str] = None


class DraftInit(BaseModel):
    month: str


class DraftItemUpdate(BaseModel):
    account_id: int
    value: Optional[float] = None
    note: Optional[str] = None


class DraftUpdate(BaseModel):
    month: str
    items: list[DraftItemUpdate]


class DraftPublish(BaseModel):
    month: str


TYPE_LABELS = {
    "courant": "Comptes courants",
    "epargne": "Épargne",
    "livret": "Livrets",
    "cto": "CTO",
    "pea": "PEA",
    "per": "PER",
    "assurance_vie": "Assurance-vie",
    "immobilier": "Immobilier",
    "credit": "Crédits",
    "autre_actif": "Autres actifs",
    "autre_passif": "Autres passifs",
}

TYPE_ORDER = [
    "courant",
    "livret",
    "epargne",
    "cto",
    "pea",
    "assurance_vie",
    "per",
    "immobilier",
    "credit",
    "autre_actif",
    "autre_passif",
]


def _validate_month(month: str) -> str:
    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", month):
        raise HTTPException(status_code=422, detail="month must use YYYY-MM")
    return month


def _previous_month(month: str, db: Session) -> Optional[str]:
    return (
        db.query(PatrimonySnapshot.month)
        .filter(PatrimonySnapshot.month < month)
        .order_by(PatrimonySnapshot.month.desc())
        .limit(1)
        .scalar()
    )


def _draft_totals(items: list[PatrimonyDraftItem]) -> dict:
    values = [item.value for item in items if item.value is not None]
    actifs = sum(v for v in values if v > 0)
    passifs = sum(abs(v) for v in values if v < 0)
    return {
        "actifs": round(actifs, 2),
        "passifs": round(passifs, 2),
        "patrimoine_net": round(actifs - passifs, 2),
    }


def _serialize_draft(month: str, db: Session) -> dict:
    accounts = db.query(Account).filter(Account.status == AccountStatus.actif).all()
    items_map = {
        item.account_id: item
        for item in db.query(PatrimonyDraftItem).filter_by(month=month).all()
    }
    ordered_types = {key: index for index, key in enumerate(TYPE_ORDER)}
    groups = []

    for account in sorted(accounts, key=lambda acc: (
        ordered_types.get(_account_type_key(acc.type), 99),
        acc.name.lower(),
    )):
        type_key = _account_type_key(account.type)
        item = items_map.get(account.id)
        if item is None:
            continue
        group = next((g for g in groups if g["type"] == type_key), None)
        if group is None:
            group = {
                "type": type_key,
                "label": TYPE_LABELS.get(type_key, type_key),
                "items": [],
            }
            groups.append(group)
        group["items"].append({
            "account_id": account.id,
            "account_name": account.name,
            "account_type": type_key,
            "bank": account.bank,
            "members": [m.first_name for m in account.members],
            "value": item.value,
            "note": item.note,
            "source_month": item.source_month,
            "source_value": item.source_value,
        })

    items = list(items_map.values())
    return {"month": month, "groups": groups, "totals": _draft_totals(items)}


@router.get("/months")
def list_months(db: Session = Depends(get_db)):
    """Liste les mois disponibles jusqu'au mois courant (pour le sélecteur)."""
    rows = (
        db.query(distinct(PatrimonySnapshot.month))
        .filter(PatrimonySnapshot.month <= TODAY)
        .order_by(PatrimonySnapshot.month.desc())
        .all()
    )
    return [r[0] for r in rows]


@router.get("/drafts")
def list_drafts(db: Session = Depends(get_db)):
    rows = (
        db.query(distinct(PatrimonyDraftItem.month))
        .order_by(PatrimonyDraftItem.month.desc())
        .all()
    )
    return [r[0] for r in rows]


@router.get("/draft")
def get_draft(month: str, db: Session = Depends(get_db)):
    month = _validate_month(month)
    exists = db.query(PatrimonyDraftItem.id).filter_by(month=month).first()
    if not exists:
        raise HTTPException(status_code=404, detail="draft not found")
    return _serialize_draft(month, db)


@router.post("/draft")
def init_draft(body: DraftInit, db: Session = Depends(get_db)):
    month = _validate_month(body.month)
    published = db.query(PatrimonySnapshot.id).filter_by(month=month).first()
    if published:
        raise HTTPException(status_code=409, detail="month is already published")

    existing = db.query(PatrimonyDraftItem.id).filter_by(month=month).first()
    if existing:
        return _serialize_draft(month, db)

    accounts = db.query(Account).filter(Account.status == AccountStatus.actif).all()
    source_month = _previous_month(month, db)
    source_values = {}
    if source_month:
        source_values = {
            snap.account_id: snap.value
            for snap in db.query(PatrimonySnapshot).filter_by(month=source_month).all()
        }

    for account in accounts:
        source_value = source_values.get(account.id)
        value = source_value if source_value is not None else account.initial_balance
        db.add(PatrimonyDraftItem(
            account_id=account.id,
            month=month,
            value=value,
            source_month=source_month,
            source_value=source_value,
            note="Prérempli depuis le mois précédent" if source_month else "Prérempli depuis le solde initial",
        ))

    db.commit()
    return _serialize_draft(month, db)


@router.put("/draft")
def update_draft(body: DraftUpdate, db: Session = Depends(get_db)):
    month = _validate_month(body.month)
    existing = {
        item.account_id: item
        for item in db.query(PatrimonyDraftItem).filter_by(month=month).all()
    }
    if not existing:
        raise HTTPException(status_code=404, detail="draft not found")

    for update in body.items:
        item = existing.get(update.account_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"draft item not found for account {update.account_id}")
        item.value = update.value
        item.note = update.note

    db.commit()
    return _serialize_draft(month, db)


@router.post("/draft/publish")
def publish_draft(body: DraftPublish, db: Session = Depends(get_db)):
    month = _validate_month(body.month)
    published = db.query(PatrimonySnapshot.id).filter_by(month=month).first()
    if published:
        raise HTTPException(status_code=409, detail="month is already published")

    items = db.query(PatrimonyDraftItem).filter_by(month=month).all()
    if not items:
        raise HTTPException(status_code=404, detail="draft not found")

    missing = [item.account_id for item in items if item.value is None]
    if missing:
        raise HTTPException(status_code=422, detail={"missing_account_ids": missing})

    for item in items:
        db.add(PatrimonySnapshot(
            account_id=item.account_id,
            month=month,
            value=item.value,
            note=item.note or "Validé depuis draft patrimoine",
        ))
        db.delete(item)

    db.commit()
    return {"ok": True, "month": month, "published_items": len(items)}


@router.get("/snapshot")
def get_snapshot(month: str, db: Session = Depends(get_db)):
    """
    Retourne les valeurs de tous les comptes pour un mois donné.
    Si un compte n'a pas de snapshot pour ce mois, retourne None.
    """
    accounts = db.query(Account).filter(Account.status == AccountStatus.actif).all()
    snaps_map = {
        s.account_id: s.value
        for s in db.query(PatrimonySnapshot).filter_by(month=month).all()
    }

    result = []
    for acc in accounts:
        value = snaps_map.get(acc.id)
        result.append({
            "account_id": acc.id,
            "account_name": acc.name,
            "account_type": acc.type,
            "bank": acc.bank,
            "members": [m.first_name for m in acc.members],
            "value": value,
            "month": month,
        })

    actifs  = sum(v for v in snaps_map.values() if v and v > 0)
    passifs = sum(abs(v) for v in snaps_map.values() if v and v < 0)

    return {
        "month": month,
        "accounts": result,
        "totals": {
            "actifs": round(actifs, 2),
            "passifs": round(passifs, 2),
            "patrimoine_net": round(actifs - passifs, 2),
        },
    }


@router.post("/snapshot")
def upsert_snapshot(body: SnapshotUpsert, db: Session = Depends(get_db)):
    """Crée une valeur publiée. Une valeur publiée existante est immuable."""
    existing = db.query(PatrimonySnapshot).filter_by(
        account_id=body.account_id, month=body.month
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail="published snapshot is immutable")
    else:
        db.add(PatrimonySnapshot(
            account_id=body.account_id,
            month=body.month,
            value=body.value,
            note=body.note,
        ))
    db.commit()
    return {"ok": True, "account_id": body.account_id, "month": body.month, "value": body.value}


@router.get("/evolution")
def patrimony_evolution(
    up_to: str = Query(default=None, description="Mois max YYYY-MM (défaut = mois courant)"),
    mode: str = Query(default="brut", pattern="^(brut|net|liquidity|metrics)$"),
    db: Session = Depends(get_db),
):
    """
    Retourne l'évolution mensuelle agrégée jusqu'au mois sélectionné.
    Par défaut limité au mois courant.
    """
    ceiling = up_to if up_to and up_to <= TODAY else TODAY
    months = (
        db.query(distinct(PatrimonySnapshot.month))
        .filter(PatrimonySnapshot.month <= ceiling)
        .order_by(PatrimonySnapshot.month.asc())
        .all()
    )

    if mode == "net":
        return _patrimony_net_evolution(db, months)
    if mode == "liquidity":
        return _patrimony_liquidity_evolution(db, months)
    if mode == "metrics":
        return _patrimony_metrics_evolution(db, months)

    result = []
    for (month,) in months:
        snaps = db.query(PatrimonySnapshot).filter_by(month=month).all()
        actifs  = sum(s.value for s in snaps if s.value and s.value > 0)
        passifs = sum(abs(s.value) for s in snaps if s.value and s.value < 0)
        net     = actifs - passifs

        y, mo = month.split("-")
        from datetime import date as dt
        label = dt(int(y), int(mo), 1).strftime("%b %y").capitalize()

        result.append({
            "month": month,
            "label": label,
            "actifs":  round(actifs, 2),
            "passifs": round(passifs, 2),
            "net":     round(net, 2),
        })

    return result


def _month_label(month: str) -> str:
    y, mo = month.split("-")
    from datetime import date as dt
    return dt(int(y), int(mo), 1).strftime("%b %y").capitalize()


def _account_type_key(account_type) -> str:
    return account_type.value if hasattr(account_type, "value") else str(account_type)


def _patrimony_net_evolution(db: Session, months) -> dict:
    accounts = db.query(Account).filter(Account.status == AccountStatus.actif).all()
    series_totals = {key: 0.0 for key, _, _ in NET_SERIES}
    points = []

    for (month,) in months:
        snaps_map = {
            s.account_id: s.value
            for s in db.query(PatrimonySnapshot).filter_by(month=month).all()
        }
        point = {"month": month, "label": _month_label(month)}
        month_values = {key: 0.0 for key, _, _ in NET_SERIES}
        immobilier = 0.0
        credit = 0.0

        for acc in accounts:
            value = snaps_map.get(acc.id)
            if value is None:
                continue
            type_key = _account_type_key(acc.type)
            if type_key == "credit" and value < 0:
                credit += abs(value)
                continue
            if value <= 0:
                continue
            if type_key == "immobilier":
                immobilier += value
            elif type_key in month_values:
                month_values[type_key] += value

        month_values["immobilier_equity"] = max(immobilier - credit, 0.0)

        for key, value in month_values.items():
            rounded = round(value, 2)
            point[key] = rounded
            series_totals[key] += rounded
        point["total"] = _snap_total(snaps_map)
        points.append(point)

    series = [
        {"key": key, "name": name, "color": color}
        for key, name, color in NET_SERIES
        if series_totals[key] > 0
    ]
    return {"mode": "net", "series": series, "points": points}


def _patrimony_liquidity_evolution(db: Session, months) -> dict:
    accounts = db.query(Account).filter(Account.status == AccountStatus.actif).all()
    series_totals = {key: 0.0 for key, _, _ in LIQUIDITY_SERIES}
    points = []

    for (month,) in months:
        snaps_map = {
            s.account_id: s.value
            for s in db.query(PatrimonySnapshot).filter_by(month=month).all()
        }

        def _sum(types):
            return sum(
                snaps_map[a.id] for a in accounts
                if _account_type_key(a.type) in types
                   and a.id in snaps_map and snaps_map[a.id] > 0
            )

        securite      = _sum(["courant", "livret", "epargne"])
        autre_actif   = _sum(["autre_actif"])
        assurance_vie = _sum(["assurance_vie"])
        cto           = _sum(["cto"])
        pea           = _sum(["pea"])
        per           = _sum(["per"])
        immobilier    = _sum(["immobilier"])
        credit        = sum(
            abs(snaps_map[a.id]) for a in accounts
            if _account_type_key(a.type) == "credit"
               and a.id in snaps_map and snaps_map[a.id] < 0
        )

        values = {
            "securite":   round(securite, 2),
            "accessible": round(autre_actif + assurance_vie + cto, 2),
            "investi_lt": round(pea + per, 2),
            "immo":       round(max(immobilier - credit, 0.0), 2),
        }
        point = {"month": month, "label": _month_label(month), "total": _snap_total(snaps_map)}
        point.update(values)
        for key, v in values.items():
            series_totals[key] += v
        points.append(point)

    series = [
        {"key": key, "name": name, "color": color}
        for key, name, color in LIQUIDITY_SERIES
        if series_totals[key] > 0
    ]
    return {"mode": "liquidity", "series": series, "points": points}


def _patrimony_metrics_evolution(db: Session, months) -> dict:
    accounts = db.query(Account).filter(Account.status == AccountStatus.actif).all()
    series_totals = {key: 0.0 for key, _, _ in METRICS_SERIES}
    points = []

    for (month,) in months:
        snaps_map = {
            s.account_id: s.value
            for s in db.query(PatrimonySnapshot).filter_by(month=month).all()
        }

        def _sum(types):
            return sum(
                snaps_map[a.id] for a in accounts
                if _account_type_key(a.type) in types
                   and a.id in snaps_map and snaps_map[a.id] > 0
            )

        securite      = _sum(["courant", "livret", "epargne"])
        autre_actif   = _sum(["autre_actif"])
        assurance_vie = _sum(["assurance_vie"])
        cto           = _sum(["cto"])
        pea           = _sum(["pea"])
        per           = _sum(["per"])
        immobilier    = _sum(["immobilier"])
        credit        = sum(
            abs(snaps_map[a.id]) for a in accounts
            if _account_type_key(a.type) == "credit"
               and a.id in snaps_map and snaps_map[a.id] < 0
        )
        immo_equity       = max(immobilier - credit, 0.0)
        capital_investi   = cto + pea + per + assurance_vie
        epargne_dispo     = securite + autre_actif + assurance_vie + cto
        investi_pl        = capital_investi + _sum(["livret", "epargne"])
        patrimoine_net    = securite + autre_actif + capital_investi + immo_equity
        patrimoine_hors_rp = patrimoine_net - immo_equity

        values = {
            "epargne_securite":     round(securite, 2),
            "epargne_dispo":        round(epargne_dispo, 2),
            "capital_investi":      round(capital_investi, 2),
            "investi_plus_livrets": round(investi_pl, 2),
            "patrimoine_hors_rp":   round(patrimoine_hors_rp, 2),
        }
        point = {"month": month, "label": _month_label(month)}
        point.update(values)
        for key, v in values.items():
            series_totals[key] += v
        points.append(point)

    series = [
        {"key": key, "name": name, "color": color}
        for key, name, color in METRICS_SERIES
        if series_totals[key] > 0
    ]
    return {"mode": "metrics", "series": series, "points": points}


@router.get("/breakdown")
def assets_breakdown(
    month: str,
    net: bool = Query(default=False, description="Mode net : immobilier déduit du prêt immo"),
    db: Session = Depends(get_db),
):
    """
    Répartition des actifs par type de compte pour un mois donné.
    net=false (défaut) : valeurs brutes
    net=true           : immobilier affiché en equity (valeur − capital restant dû)
    """
    accounts = db.query(Account).filter(Account.status == AccountStatus.actif).all()
    snaps_map = {
        s.account_id: s.value
        for s in db.query(PatrimonySnapshot).filter_by(month=month).all()
    }

    groups: dict[str, dict] = {}
    for acc in accounts:
        value = snaps_map.get(acc.id)
        if value is None or value <= 0:
            continue
        meta = ASSET_TYPE_GROUPS.get(_account_type_key(acc.type))
        if meta is None:
            continue
        name, color = meta
        if name not in groups:
            groups[name] = {"name": name, "color": color, "value": 0.0}
        groups[name]["value"] += value

    if net:
        # Déduire le capital restant dû (credit) de l'immobilier
        credit_total = sum(
            abs(snaps_map[acc.id])
            for acc in accounts
            if acc.type == "credit" and acc.id in snaps_map and snaps_map[acc.id] < 0
        )
        if "Immobilier" in groups:
            equity = groups["Immobilier"]["value"] - credit_total
            if equity > 0:
                groups["Immobilier"]["name"]  = "Immobilier (equity)"
                groups["Immobilier"]["value"] = equity
            else:
                del groups["Immobilier"]

    items = [
        {**g, "value": round(g["value"], 2)}
        for g in sorted(groups.values(), key=lambda x: x["value"], reverse=True)
        if g["value"] > 0
    ]
    return items


@router.get("/indicators")
def patrimony_indicators(month: str, db: Session = Depends(get_db)):
    """
    Indicateurs d'analyse patrimoniale pour un mois donné.
    Retourne les métriques clés + couches de liquidité pour la barre visuelle.
    """
    accounts = db.query(Account).filter(Account.status == AccountStatus.actif).all()
    snaps_map = {
        s.account_id: s.value
        for s in db.query(PatrimonySnapshot).filter_by(month=month).all()
    }

    def total(types: list[str]) -> float:
        return sum(
            snaps_map[a.id]
            for a in accounts
            if a.type in types and a.id in snaps_map and snaps_map[a.id] > 0
        )

    securite      = total(["courant", "livret", "epargne"])
    autre_actif   = total(["autre_actif"])
    assurance_vie = total(["assurance_vie"])
    cto           = total(["cto"])
    pea           = total(["pea"])
    per           = total(["per"])
    immobilier    = total(["immobilier"])
    credit        = sum(
        abs(snaps_map[a.id])
        for a in accounts
        if a.type == "credit" and a.id in snaps_map and snaps_map[a.id] < 0
    )

    immo_equity       = max(immobilier - credit, 0)
    capital_investi   = cto + pea + per + assurance_vie
    investi_lt        = pea + per
    epargne_dispo     = securite + autre_actif + assurance_vie + cto
    investi_pl        = capital_investi + total(["livret", "epargne"])
    patrimoine_net    = securite + autre_actif + capital_investi + immo_equity
    patrimoine_hors_rp = patrimoine_net - immo_equity

    # Couches pour la barre de liquidité (ordre croissant d'illiquidité)
    layers = [
        {"key": "securite",   "label": "Sécurité",     "value": round(securite, 2),    "color": "#22c55e"},
        {"key": "accessible", "label": "Accessible",   "value": round(autre_actif + assurance_vie + cto, 2), "color": "#06b6d4"},
        {"key": "investi_lt", "label": "Investi LT",   "value": round(investi_lt, 2),  "color": "#6366f1"},
        {"key": "immo",       "label": "Immo (equity)","value": round(immo_equity, 2), "color": "#f97316"},
    ]

    return {
        "month": month,
        "epargne_securite":    round(securite, 2),
        "epargne_dispo":       round(epargne_dispo, 2),
        "capital_investi":     round(capital_investi, 2),
        "investi_plus_livrets":round(investi_pl, 2),
        "patrimoine_hors_rp":  round(patrimoine_hors_rp, 2),
        "patrimoine_net":      round(patrimoine_net, 2),
        "layers":              [l for l in layers if l["value"] > 0],
    }


@router.get("/history/{account_id}")
def account_history(account_id: int, db: Session = Depends(get_db)):
    """Historique mensuel d'un compte."""
    snaps = (
        db.query(PatrimonySnapshot)
        .filter_by(account_id=account_id)
        .order_by(PatrimonySnapshot.month.asc())
        .all()
    )
    return [{"month": s.month, "value": s.value} for s in snaps]
