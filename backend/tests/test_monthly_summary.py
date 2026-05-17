"""
Tests de non-régression pour monthly_summary.

Vérifie que chaque flag (is_internal_transfer, is_neutral, is_investment,
is_compte_pro) est correctement exclu/inclus dans les agrégats.
"""
import pytest
import hashlib
from datetime import date
import api.routes.transactions as transactions_routes
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from db.models import (
    Account, FamilyMember, Category, CategoryGroup, Transaction,
    AccountType, AccountStatus, MemberRole, ProjectionMode, TransactionType,
)
from api.routes.transactions import monthly_summary


MONTH = "2025-11"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash(seed: str) -> str:
    return hashlib.md5(seed.encode()).hexdigest()[:16]


def make_tx(db, account, amount: float, tx_type: TransactionType, day: int = 1,
            category=None, **flags) -> Transaction:
    tx = Transaction(
        account_id=account.id,
        date=date(2025, 11, day),
        raw_label="TEST",
        label="test",
        amount=amount,
        transaction_type=tx_type,
        category_id=category.id if category else None,
        import_hash=_hash(f"{amount}{tx_type}{day}{list(flags)}"),
        **flags,
    )
    db.add(tx)
    db.commit()
    return tx


def make_tx_on(db, account, tx_date: date, amount: float, tx_type: TransactionType,
               category=None, **flags) -> Transaction:
    tx = Transaction(
        account_id=account.id,
        date=tx_date,
        raw_label=f"TEST {tx_date.isoformat()} {amount}",
        label=f"test {tx_date.isoformat()} {amount}",
        amount=amount,
        transaction_type=tx_type,
        category_id=category.id if category else None,
        import_hash=_hash(f"{tx_date}{amount}{tx_type}{category.id if category else 'none'}{list(flags)}"),
        **flags,
    )
    db.add(tx)
    db.commit()
    return tx


def make_group_with_category(db, name: str, mode: ProjectionMode, budget_annual: float = 1200.0):
    group = CategoryGroup(
        name=name,
        color="#ffffff",
        budget_annual=budget_annual,
        projection_mode=mode,
    )
    category = Category(name=f"{name} cat", color="#ffffff", group=group)
    db.add(group)
    db.add(category)
    db.commit()
    return group, category


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def account(db):
    member = FamilyMember(first_name="Test", role=MemberRole.owner)
    db.add(member)
    acc = Account(
        name="CC Test", type=AccountType.courant, bank="Test",
        status=AccountStatus.actif,
    )
    acc.members = [member]
    db.add(acc)
    db.commit()
    return acc


# ── Tests dépenses ────────────────────────────────────────────────────────────

def test_depense_normale_comptee(db, account):
    """Un débit ordinaire doit être compté dans depenses."""
    make_tx(db, account, 100.0, TransactionType.debit)
    result = monthly_summary(MONTH, db)
    assert result["depenses"] == 100.0


def test_internal_transfer_exclu_depenses(db, account):
    """is_internal_transfer=True → exclu des dépenses."""
    make_tx(db, account, 500.0, TransactionType.debit, is_internal_transfer=True)
    result = monthly_summary(MONTH, db)
    assert result["depenses"] == 0.0


def test_neutral_exclu_depenses(db, account):
    """is_neutral=True → exclu des dépenses."""
    make_tx(db, account, 200.0, TransactionType.debit, is_neutral=True)
    result = monthly_summary(MONTH, db)
    assert result["depenses"] == 0.0


def test_investment_exclu_depenses(db, account):
    """is_investment=True → exclu des dépenses (compté dans investissements)."""
    make_tx(db, account, 300.0, TransactionType.debit, is_investment=True)
    result = monthly_summary(MONTH, db)
    assert result["depenses"] == 0.0
    assert result["investissements"] == 300.0


def test_compte_pro_exclu_depenses(db, account):
    """is_compte_pro=True → exclu des dépenses (déduit des revenus)."""
    make_tx(db, account, 1500.0, TransactionType.debit, is_compte_pro=True)
    result = monthly_summary(MONTH, db)
    assert result["depenses"] == 0.0


def test_mix_normal_et_flags(db, account):
    """Seules les tx normales comptent dans depenses, pas les flaguées."""
    make_tx(db, account, 100.0, TransactionType.debit)                             # comptée
    make_tx(db, account, 500.0, TransactionType.debit, is_internal_transfer=True)  # exclue
    make_tx(db, account, 200.0, TransactionType.debit, is_neutral=True)            # exclue
    make_tx(db, account, 300.0, TransactionType.debit, is_investment=True)         # exclue
    make_tx(db, account, 1500.0, TransactionType.debit, is_compte_pro=True)        # exclue
    result = monthly_summary(MONTH, db)
    assert result["depenses"] == 100.0
    assert result["investissements"] == 300.0


# ── Tests revenus / apports pro ───────────────────────────────────────────────

def test_compte_pro_deduit_revenus(db, account):
    """is_compte_pro=True → déduit des revenus bruts."""
    make_tx(db, account, 3000.0, TransactionType.credit)   # revenu
    make_tx(db, account, 500.0, TransactionType.debit, is_compte_pro=True)  # apport pro
    result = monthly_summary(MONTH, db)
    assert result["revenus_bruts"] == 3000.0
    assert result["apports_pro"] == 500.0
    assert result["revenus"] == 2500.0


def test_internal_transfer_non_deduit_revenus(db, account):
    """is_internal_transfer seul (sans is_compte_pro) ne déduit pas les revenus."""
    make_tx(db, account, 3000.0, TransactionType.credit)
    make_tx(db, account, 500.0, TransactionType.debit, is_internal_transfer=True)
    result = monthly_summary(MONTH, db)
    assert result["apports_pro"] == 0.0
    assert result["revenus"] == 3000.0


# ── Tests virements internes ──────────────────────────────────────────────────

def test_virement_interne_compte(db, account):
    """is_internal_transfer=True → compté dans virements_envoyes."""
    make_tx(db, account, 400.0, TransactionType.debit, is_internal_transfer=True)
    result = monthly_summary(MONTH, db)
    assert result["virements_envoyes"] == 400.0


def test_compte_pro_exclu_virements_internes(db, account):
    """is_compte_pro=True → NON compté dans virements_envoyes (était le bug)."""
    make_tx(db, account, 1500.0, TransactionType.debit, is_compte_pro=True)
    result = monthly_summary(MONTH, db)
    assert result["virements_envoyes"] == 0.0
    assert result["virements_recus"] == 0.0


def test_neutral_exclu_virements_internes(db, account):
    """is_neutral=True → non compté dans virements internes même si is_internal_transfer."""
    make_tx(db, account, 200.0, TransactionType.debit,
            is_internal_transfer=True, is_neutral=True)
    result = monthly_summary(MONTH, db)
    assert result["virements_envoyes"] == 0.0


def test_virement_interne_recus(db, account):
    """Crédit is_internal_transfer → compté dans virements_recus."""
    make_tx(db, account, 1000.0, TransactionType.credit, is_internal_transfer=True)
    result = monthly_summary(MONTH, db)
    assert result["virements_recus"] == 1000.0


# ── Test investissements ───────────────────────────────────────────────────────

def test_investissement_dans_widget(db, account):
    """is_investment → apparaît dans investissements, pas dans depenses."""
    make_tx(db, account, 500.0, TransactionType.debit, is_investment=True)
    make_tx(db, account, 100.0, TransactionType.debit)
    result = monthly_summary(MONTH, db)
    assert result["investissements"] == 500.0
    assert result["depenses"] == 100.0


def test_pas_investissements_si_aucun(db, account):
    """Sans is_investment, investissements = 0."""
    make_tx(db, account, 100.0, TransactionType.debit)
    result = monthly_summary(MONTH, db)
    assert result["investissements"] == 0.0


# ── Tests projections mois courant ────────────────────────────────────────────

def test_projection_linear_lisse_sur_avancement_du_mois(db, account, monkeypatch):
    """linear → projection = dépensé × pace_factor."""
    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2025, 11, 10)

    monkeypatch.setattr(transactions_routes, "date", FakeDate)
    _, category = make_group_with_category(db, "Alimentation test", ProjectionMode.linear)
    make_tx_on(db, account, date(2025, 11, 5), 100.0, TransactionType.debit, category=category)

    result = monthly_summary(MONTH, db)
    group = next(g for g in result["groups"] if g["name"] == "Alimentation test")

    assert result["pace_factor"] == 3.0
    assert group["projection_mode"] == "linear"
    assert group["projection_amount"] == 300.0
    assert group["projection_source"] == "pace"


def test_projection_fixed_historical_ne_lisse_pas_un_paiement_constate(db, account, monkeypatch):
    """fixed_historical avec paiement déjà passé → projection = réel actuel."""
    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2025, 11, 10)

    monkeypatch.setattr(transactions_routes, "date", FakeDate)
    _, category = make_group_with_category(db, "Logement test", ProjectionMode.fixed_historical)
    make_tx_on(db, account, date(2025, 11, 3), 900.0, TransactionType.debit, category=category)

    result = monthly_summary(MONTH, db)
    group = next(g for g in result["groups"] if g["name"] == "Logement test")

    assert group["total"] == 900.0
    assert group["projection_amount"] == 900.0
    assert group["projection_source"] == "actual_paid"


def test_projection_fixed_historical_utilise_moyenne_6_mois_avant_paiement(db, account, monkeypatch):
    """fixed_historical sans paiement courant → projection = moyenne mensuelle 6 mois."""
    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2025, 11, 10)

    monkeypatch.setattr(transactions_routes, "date", FakeDate)
    _, category = make_group_with_category(db, "Abonnements test", ProjectionMode.fixed_historical)
    for month in range(5, 11):
        make_tx_on(db, account, date(2025, month, 3), 60.0, TransactionType.debit, category=category)

    result = monthly_summary(MONTH, db)
    group = next(g for g in result["groups"] if g["name"] == "Abonnements test")

    assert group["total"] == 0
    assert group["projection_amount"] == 60.0
    assert group["projection_source"] == "historical_6m"


def test_projection_actual_only_ne_projette_pas(db, account, monkeypatch):
    """actual_only → projection = réel, sans lissage ni historique."""
    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2025, 11, 10)

    monkeypatch.setattr(transactions_routes, "date", FakeDate)
    _, category = make_group_with_category(db, "Vacances test", ProjectionMode.actual_only)
    make_tx_on(db, account, date(2025, 11, 4), 200.0, TransactionType.debit, category=category)

    result = monthly_summary(MONTH, db)
    group = next(g for g in result["groups"] if g["name"] == "Vacances test")

    assert group["projection_amount"] == 200.0
    assert group["projection_source"] == "actual_only"
