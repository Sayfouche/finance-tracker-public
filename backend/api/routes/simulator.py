from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List
from db.database import get_db
from db.models import SimulatorConfig, Account, AccountStatus
from api.routes.accounts import _latest_balance

router = APIRouter(prefix="/simulator", tags=["simulator"])

_INVESTMENT_TYPES = ["pea", "cto", "per", "assurance_vie"]


class ConfigUpdate(BaseModel):
    monthly_contribution: float
    annual_rate: float
    account_types: List[str]
    milestone_step: float
    milestone_max: float


def _migrate(db: Session) -> None:
    """Add new columns to existing simulator_config rows (SQLite idempotent)."""
    for col, default in [("milestone_step", 100000), ("milestone_max", 1000000)]:
        try:
            db.execute(text(f"ALTER TABLE simulator_config ADD COLUMN {col} FLOAT DEFAULT {default}"))
            db.commit()
        except Exception:
            pass


def _get_or_create(db: Session) -> SimulatorConfig:
    _migrate(db)
    cfg = db.query(SimulatorConfig).filter_by(id=1).first()
    if cfg:
        return cfg
    cfg = SimulatorConfig(
        id=1,
        monthly_contribution=round(_investment_monthly_avg(db), 2),
        annual_rate=8.0,
        account_types=list(_INVESTMENT_TYPES),
        milestone_step=100000.0,
        milestone_max=1000000.0,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def _investment_monthly_avg(db: Session) -> float:
    rows = db.execute(
        text("""
            SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total
            FROM transactions
            WHERE is_investment = 1 AND transaction_type = 'debit'
            GROUP BY month
            ORDER BY month DESC
            LIMIT 3
        """)
    ).fetchall()
    if not rows:
        return 500.0
    return sum(r.total for r in rows) / len(rows)


def _starting_capital(db: Session, account_types: list) -> float:
    accounts = db.query(Account).filter(
        Account.status == AccountStatus.actif,
        Account.type.in_(account_types),
    ).all()
    return round(sum(_latest_balance(db, a) or 0.0 for a in accounts), 2)


@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    cfg = _get_or_create(db)

    selectable_types = [
        "pea", "cto", "per", "assurance_vie",
        "livret", "epargne", "courant", "immobilier", "autre_actif",
    ]
    accounts = db.query(Account).filter(
        Account.status == AccountStatus.actif,
        Account.type.in_(selectable_types),
    ).all()

    available_accounts = [
        {
            "id": a.id,
            "name": a.name,
            "type": a.type.value,
            "balance": round(_latest_balance(db, a) or 0.0, 2),
        }
        for a in accounts
    ]

    return {
        "monthly_contribution": cfg.monthly_contribution,
        "annual_rate": cfg.annual_rate,
        "account_types": cfg.account_types,
        "milestone_step": cfg.milestone_step or 100000.0,
        "milestone_max": cfg.milestone_max or 1000000.0,
        "starting_capital": _starting_capital(db, cfg.account_types),
        "available_accounts": available_accounts,
    }


@router.put("/config")
def update_config(body: ConfigUpdate, db: Session = Depends(get_db)):
    cfg = _get_or_create(db)
    cfg.monthly_contribution = body.monthly_contribution
    cfg.annual_rate = body.annual_rate
    cfg.account_types = body.account_types
    cfg.milestone_step = body.milestone_step
    cfg.milestone_max = body.milestone_max
    db.commit()
    return {"ok": True}
