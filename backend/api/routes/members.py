from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import FamilyMember, MemberRole

router = APIRouter(prefix="/members", tags=["members"])


class MemberCreate(BaseModel):
    first_name: str
    role: MemberRole = MemberRole.owner


@router.get("/")
def list_members(db: Session = Depends(get_db)):
    return [
        {"id": m.id, "first_name": m.first_name, "role": m.role}
        for m in db.query(FamilyMember).order_by(FamilyMember.id.asc()).all()
    ]


@router.post("/", status_code=201)
def create_member(body: MemberCreate, db: Session = Depends(get_db)):
    first_name = body.first_name.strip()
    if not first_name:
        raise HTTPException(status_code=422, detail="first_name is required")
    existing = db.query(FamilyMember).filter_by(first_name=first_name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Member already exists")
    member = FamilyMember(first_name=first_name, role=body.role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return {"id": member.id, "first_name": member.first_name, "role": member.role}
