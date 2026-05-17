"""
Fixtures partagées par tous les tests.
Utilise une base SQLite en mémoire isolée — jamais la vraie DB.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.database import Base
from db.models import (
    FamilyMember, Account, Category, CategoryRule,
    MemberRole, AccountType, AccountStatus, RuleMatchType, RuleSource
)
from datetime import date


@pytest.fixture(scope="function")
def db():
    """Base SQLite en mémoire, recréée à chaque test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def seeded_db(db):
    """Base avec seed complet (membres + comptes + catégories + règles)."""
    from db.seed import run_seed
    run_seed(db)
    return db


@pytest.fixture
def sample_member(db):
    m = FamilyMember(first_name="Alex", role=MemberRole.owner)
    db.add(m)
    db.commit()
    return m


@pytest.fixture
def sample_account(db, sample_member):
    acc = Account(
        name="Compte Demo A Test",
        type=AccountType.courant,
        bank="Demo Bank A",
        initial_balance=1000.0,
        start_date=date(2025, 1, 1),
        status=AccountStatus.actif,
    )
    acc.members = [sample_member]
    db.add(acc)
    db.commit()
    return acc


@pytest.fixture
def sample_categories(db):
    cats = {}
    for name, color in [("Alimentation", "#22c55e"), ("Transport", "#f59e0b"), ("Autre", "#6b7280")]:
        c = Category(name=name, color=color, is_system=True)
        db.add(c)
        cats[name] = c
    db.commit()
    return cats
