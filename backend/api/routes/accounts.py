from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date
from typing import Optional
from db.database import get_db
from db.models import Account, FamilyMember, PatrimonySnapshot, AccountStatus, AccountType

router = APIRouter(prefix="/accounts", tags=["accounts"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    name: str
    type: AccountType
    bank: Optional[str] = None
    currency: str = "EUR"
    initial_balance: float = 0.0
    start_date: Optional[date] = None
    notes: Optional[str] = None
    member_ids: list[int] = []


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    bank: Optional[str] = None
    status: Optional[AccountStatus] = None
    notes: Optional[str] = None


class AccountOut(BaseModel):
    id: int
    name: str
    type: str
    bank: Optional[str]
    currency: str
    initial_balance: float
    start_date: Optional[date]
    status: str
    notes: Optional[str]
    members: list[dict]
    current_balance: Optional[float]

    model_config = {"from_attributes": True}


def _latest_balance(db: Session, account: Account) -> Optional[float]:
    """Retourne le solde du dernier snapshot disponible, ou initial_balance."""
    snap = (
        db.query(PatrimonySnapshot)
        .filter_by(account_id=account.id)
        .order_by(PatrimonySnapshot.month.desc())
        .first()
    )
    return snap.value if snap else account.initial_balance


def _serialize(db: Session, acc: Account) -> dict:
    return {
        "id": acc.id,
        "name": acc.name,
        "type": acc.type,
        "bank": acc.bank,
        "currency": acc.currency,
        "initial_balance": acc.initial_balance,
        "start_date": acc.start_date,
        "status": acc.status,
        "notes": acc.notes,
        "members": [{"id": m.id, "first_name": m.first_name, "role": m.role} for m in acc.members],
        "current_balance": _latest_balance(db, acc),
    }


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/")
def list_accounts(db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(Account.status != AccountStatus.archive).all()
    return [_serialize(db, a) for a in accounts]


@router.get("/types")
def list_account_types():
    return [{"value": account_type.value, "label": account_type.value} for account_type in AccountType]


@router.get("/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db)):
    acc = db.query(Account).filter_by(id=account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    return _serialize(db, acc)


@router.post("/", status_code=201)
def create_account(body: AccountCreate, db: Session = Depends(get_db)):
    members = db.query(FamilyMember).filter(FamilyMember.id.in_(body.member_ids)).all()
    acc = Account(
        name=body.name, type=body.type, bank=body.bank,
        currency=body.currency, initial_balance=body.initial_balance,
        start_date=body.start_date, notes=body.notes,
        status=AccountStatus.actif,
    )
    acc.members = members
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return _serialize(db, acc)


@router.put("/{account_id}")
def update_account(account_id: int, body: AccountUpdate, db: Session = Depends(get_db)):
    acc = db.query(Account).filter_by(id=account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(acc, field, value)
    db.commit()
    return _serialize(db, acc)


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db)):
    acc = db.query(Account).filter_by(id=account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    acc.status = AccountStatus.archive
    db.commit()


@router.get("/summary/totals")
def get_totals(db: Session = Depends(get_db)):
    """Retourne actifs, passifs et patrimoine net."""
    accounts = db.query(Account).filter(Account.status == AccountStatus.actif).all()
    actifs = passifs = 0.0
    for acc in accounts:
        bal = _latest_balance(db, acc)
        if bal is None:
            continue
        if bal >= 0:
            actifs += bal
        else:
            passifs += abs(bal)
    return {
        "actifs": round(actifs, 2),
        "passifs": round(passifs, 2),
        "patrimoine_net": round(actifs - passifs, 2),
    }
