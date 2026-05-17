from datetime import date

from db.models import (
    Account,
    AccountStatus,
    AccountType,
    FamilyMember,
    MemberRole,
    PatrimonyDraftItem,
    PatrimonySnapshot,
)
from api.routes.patrimony import DraftInit, DraftItemUpdate, DraftPublish, DraftUpdate
from api.routes.patrimony import init_draft, list_months, patrimony_evolution, publish_draft, update_draft


def _member(db):
    member = FamilyMember(first_name="Test", role=MemberRole.owner)
    db.add(member)
    db.commit()
    return member


def _account(db, member, name: str, account_type: AccountType):
    account = Account(
        name=name,
        type=account_type,
        status=AccountStatus.actif,
        start_date=date(2025, 1, 1),
    )
    account.members = [member]
    db.add(account)
    db.commit()
    return account


def _snapshot(db, account, month: str, value: float):
    db.add(PatrimonySnapshot(account_id=account.id, month=month, value=value))
    db.commit()


def test_patrimony_evolution_brut_keeps_existing_shape(db):
    member = _member(db)
    current = _account(db, member, "Courant", AccountType.courant)
    credit = _account(db, member, "Crédit", AccountType.credit)
    _snapshot(db, current, "2025-01", 10000)
    _snapshot(db, credit, "2025-01", -4000)

    result = patrimony_evolution(up_to="2025-01", mode="brut", db=db)

    assert result == [{
        "month": "2025-01",
        "label": "Jan 25",
        "actifs": 10000,
        "passifs": 4000,
        "net": 6000,
    }]


def test_patrimony_evolution_net_returns_asset_series_with_immo_equity(db):
    member = _member(db)
    immo = _account(db, member, "Maison", AccountType.immobilier)
    credit = _account(db, member, "Crédit", AccountType.credit)
    livret = _account(db, member, "Livret", AccountType.livret)
    cto = _account(db, member, "CTO", AccountType.cto)
    _snapshot(db, immo, "2025-01", 500000)
    _snapshot(db, credit, "2025-01", -420000)
    _snapshot(db, livret, "2025-01", 20000)
    _snapshot(db, cto, "2025-01", 15000)

    result = patrimony_evolution(up_to="2025-01", mode="net", db=db)
    point = result["points"][0]

    assert result["mode"] == "net"
    assert {s["key"] for s in result["series"]} == {"immobilier_equity", "livret", "cto"}
    assert point["immobilier_equity"] == 80000
    assert point["livret"] == 20000
    assert point["cto"] == 15000


def test_patrimony_draft_is_prefilled_and_hidden_until_publish(db):
    member = _member(db)
    current = _account(db, member, "Courant", AccountType.courant)
    livret = _account(db, member, "Livret", AccountType.livret)
    _snapshot(db, current, "2026-04", 1000)
    _snapshot(db, livret, "2026-04", 200)

    draft = init_draft(DraftInit(month="2026-05"), db=db)

    assert list_months(db=db) == ["2026-04"]
    assert db.query(PatrimonyDraftItem).filter_by(month="2026-05").count() == 2
    values = {
        item["account_name"]: item["value"]
        for group in draft["groups"]
        for item in group["items"]
    }
    assert values == {"Courant": 1000, "Livret": 200}


def test_patrimony_draft_update_then_publish_makes_month_visible(db):
    member = _member(db)
    current = _account(db, member, "Courant", AccountType.courant)
    _snapshot(db, current, "2026-04", 1000)
    init_draft(DraftInit(month="2026-05"), db=db)

    update_draft(
        DraftUpdate(
            month="2026-05",
            items=[DraftItemUpdate(account_id=current.id, value=1250, note="Saisie manuelle")],
        ),
        db=db,
    )
    result = publish_draft(DraftPublish(month="2026-05"), db=db)

    assert result == {"ok": True, "month": "2026-05", "published_items": 1}
    assert list_months(db=db) == ["2026-05", "2026-04"]
    assert db.query(PatrimonyDraftItem).count() == 0
    snap = db.query(PatrimonySnapshot).filter_by(account_id=current.id, month="2026-05").one()
    assert snap.value == 1250
    assert snap.note == "Saisie manuelle"
