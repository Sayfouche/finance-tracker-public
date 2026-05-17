import hashlib
from datetime import date
from pathlib import Path

from db.database import Base, SessionLocal, engine
from db.models import (
    Account,
    AccountStatus,
    AccountType,
    Category,
    CategoryGroup,
    CloudSave,
    ExternalTransaction,
    FamilyMember,
    MemberRole,
    PatrimonySnapshot,
    Transaction,
    TransactionType,
)
from db.seed import run_seed


GROUPS = [
    ("Alimentation", "#22c55e", 1, ["Alimentation"], 9000),
    ("Logement", "#3b82f6", 2, ["Logement"], 18000),
    ("Transport", "#f59e0b", 3, ["Transport"], 3600),
    ("Abonnements", "#8b5cf6", 4, ["Telecom", "Abonnements"], 2400),
    ("Famille", "#f472b6", 5, ["Enfants"], 6000),
    ("Sante", "#ef4444", 6, ["Santé"], 2400),
    ("Loisirs", "#06b6d4", 7, ["Loisirs"], 4800),
    ("Impots", "#94a3b8", 8, ["Impôts"], 5000),
    ("Investissement", "#6366f1", 9, ["Épargne", "Investissement"], None),
    ("Autre", "#6b7280", 10, ["Autre", "Banque"], 2400),
]

TRANSACTIONS = [
    ("2026-05-03", "Salaire Demo", 4200.00, "credit", "Revenus"),
    ("2026-05-04", "Loyer Demo", 1450.00, "debit", "Logement"),
    ("2026-05-05", "Carrefour Demo", 92.40, "debit", "Alimentation"),
    ("2026-05-06", "Navigo Demo", 86.40, "debit", "Transport"),
    ("2026-05-08", "Netflix Demo", 17.99, "debit", "Abonnements"),
    ("2026-05-10", "Pharmacie Demo", 28.70, "debit", "Santé"),
    ("2026-05-12", "Restaurant Demo", 64.30, "debit", "Loisirs"),
    ("2026-04-03", "Salaire Demo", 4200.00, "credit", "Revenus"),
    ("2026-04-04", "Loyer Demo", 1450.00, "debit", "Logement"),
    ("2026-04-07", "Courses Demo", 388.20, "debit", "Alimentation"),
    ("2026-04-10", "Ecole Demo", 210.00, "debit", "Enfants"),
    ("2026-04-12", "Versement ETF Demo", 500.00, "debit", "Investissement"),
    ("2026-03-03", "Salaire Demo", 4150.00, "credit", "Revenus"),
    ("2026-03-04", "Loyer Demo", 1450.00, "debit", "Logement"),
    ("2026-03-11", "Train Demo", 74.00, "debit", "Transport"),
    ("2026-03-18", "Impots Demo", 420.00, "debit", "Impôts"),
]

SNAPSHOTS = {
    "2026-01": {
        "Compte courant Demo": 2200,
        "Livret Demo": 11800,
        "Portefeuille ETF Demo": 7200,
        "Appartement Demo": 320000,
        "Credit immobilier Demo": -248000,
    },
    "2026-02": {
        "Compte courant Demo": 2600,
        "Livret Demo": 12100,
        "Portefeuille ETF Demo": 7550,
        "Appartement Demo": 321000,
        "Credit immobilier Demo": -246900,
    },
    "2026-03": {
        "Compte courant Demo": 1950,
        "Livret Demo": 12400,
        "Portefeuille ETF Demo": 7900,
        "Appartement Demo": 322000,
        "Credit immobilier Demo": -245800,
    },
    "2026-04": {
        "Compte courant Demo": 2850,
        "Livret Demo": 12700,
        "Portefeuille ETF Demo": 8200,
        "Appartement Demo": 323000,
        "Credit immobilier Demo": -244700,
    },
    "2026-05": {
        "Compte courant Demo": 3100,
        "Livret Demo": 13000,
        "Portefeuille ETF Demo": 8500,
        "Appartement Demo": 324000,
        "Credit immobilier Demo": -243600,
    },
}


def _hash(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()[:32]


def _category_by_name(db, name: str) -> Category | None:
    return db.query(Category).filter_by(name=name).first()


def _account_by_name(db, name: str) -> Account:
    account = db.query(Account).filter_by(name=name).first()
    if not account:
        raise RuntimeError(f"Missing seeded account: {name}")
    return account


def seed_demo_members(db) -> dict[str, FamilyMember]:
    members_data = [
        ("Alex", MemberRole.owner),
        ("Sam", MemberRole.spouse),
        ("Charlie", MemberRole.child),
    ]
    members: dict[str, FamilyMember] = {}
    for first_name, role in members_data:
        member = db.query(FamilyMember).filter_by(first_name=first_name).first()
        if not member:
            member = FamilyMember(first_name=first_name, role=role)
            db.add(member)
            db.flush()
        members[first_name] = member
    return members


def seed_demo_accounts(db) -> None:
    members = seed_demo_members(db)
    household = [members["Alex"], members["Sam"]]
    accounts_data = [
        ("Compte courant Demo", AccountType.courant, "Demo Bank", [members["Alex"]], 2200.0),
        ("Livret Demo", AccountType.livret, "Demo Bank", household, 11800.0),
        ("Portefeuille ETF Demo", AccountType.cto, "Demo Broker", [members["Alex"]], 7200.0),
        ("Appartement Demo", AccountType.immobilier, None, household, 320000.0),
        ("Credit immobilier Demo", AccountType.credit, "Demo Bank", household, -248000.0),
    ]
    for name, account_type, bank, account_members, initial_balance in accounts_data:
        account = db.query(Account).filter_by(name=name).first()
        if not account:
            account = Account(
                name=name,
                type=account_type,
                bank=bank,
                initial_balance=initial_balance,
                start_date=date(2026, 1, 1),
                status=AccountStatus.actif,
            )
            db.add(account)
        account.members = account_members
    db.flush()


def seed_groups(db) -> None:
    for name, color, sort_order, category_names, budget_annual in GROUPS:
        group = db.query(CategoryGroup).filter_by(name=name).first()
        if not group:
            group = CategoryGroup(name=name)
            db.add(group)
            db.flush()
        group.color = color
        group.sort_order = sort_order
        group.budget_annual = budget_annual
        group.exclude_from_budget = name == "Investissement"

        for category_name in category_names:
            category = _category_by_name(db, category_name)
            if category:
                category.group_id = group.id


def reset_demo_facts(db) -> None:
    db.query(ExternalTransaction).delete()
    db.query(Transaction).delete()
    db.query(PatrimonySnapshot).delete()
    db.query(CloudSave).delete()
    db.commit()


def seed_transactions(db) -> None:
    account = _account_by_name(db, "Compte courant Demo")
    for tx_date, label, amount, tx_type, category_name in TRANSACTIONS:
        category = _category_by_name(db, category_name)
        tx = Transaction(
            account_id=account.id,
            date=date.fromisoformat(tx_date),
            raw_label=label.upper(),
            label=label.lower(),
            amount=amount,
            transaction_type=TransactionType(tx_type),
            category_id=category.id if category else None,
            category_source="manual" if category else None,
            is_investment=category_name == "Investissement",
            import_hash=_hash("demo", tx_date, label, amount, tx_type),
        )
        db.add(tx)


def seed_snapshots(db) -> None:
    for month, values in SNAPSHOTS.items():
        for account_name, value in values.items():
            account = _account_by_name(db, account_name)
            db.add(PatrimonySnapshot(
                account_id=account.id,
                month=month,
                value=value,
                note="Demo mock data",
            ))


def seed_cloud_saves(db) -> None:
    db.add(CloudSave(
        name="Demo baseline",
        description="Point de rollback demo mock",
        github_sha="demo-local",
        github_url=None,
        size_bytes=None,
    ))


def main() -> None:
    database = engine.url.database
    if database and database != ":memory:":
        Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run_seed(db)
        seed_demo_accounts(db)
        seed_groups(db)
        reset_demo_facts(db)
        seed_transactions(db)
        seed_snapshots(db)
        seed_cloud_saves(db)
        db.commit()
        print("Demo DB seeded with mock data")
    finally:
        db.close()


if __name__ == "__main__":
    main()
