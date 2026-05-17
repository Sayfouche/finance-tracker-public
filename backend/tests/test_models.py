"""Tests des modèles de données et du seed initial."""
import pytest
from datetime import date
from db.models import (
    FamilyMember, Account, Category, CategoryRule, PatrimonySnapshot, Settings,
    MemberRole, AccountType, AccountStatus, RuleSource
)


class TestFamilyMember:
    def test_create_member(self, db):
        m = FamilyMember(first_name="Alex", role=MemberRole.owner)
        db.add(m)
        db.commit()
        assert m.id is not None
        assert m.first_name == "Alex"
        assert m.role == MemberRole.owner

    def test_all_roles(self, db):
        for name, role in [("Alex", MemberRole.owner), ("Sam", MemberRole.spouse), ("Charlie", MemberRole.child)]:
            db.add(FamilyMember(first_name=name, role=role))
        db.commit()
        assert db.query(FamilyMember).count() == 3


class TestAccount:
    def test_create_account(self, db, sample_member):
        acc = Account(
            name="Compte Demo A",
            type=AccountType.courant,
            bank="Demo Bank A",
            initial_balance=5000.0,
            start_date=date(2025, 1, 1),
            status=AccountStatus.actif,
        )
        acc.members = [sample_member]
        db.add(acc)
        db.commit()

        assert acc.id is not None
        assert acc.name == "Compte Demo A"
        assert acc.initial_balance == 5000.0
        assert len(acc.members) == 1

    def test_account_multiple_members(self, db):
        owner = FamilyMember(first_name="Alex", role=MemberRole.owner)
        partner = FamilyMember(first_name="Sam", role=MemberRole.spouse)
        db.add_all([owner, partner])
        db.flush()

        acc = Account(
            name="Résidence principale",
            type=AccountType.immobilier,
            initial_balance=480000.0,
        )
        acc.members = [owner, partner]
        db.add(acc)
        db.commit()

        assert len(acc.members) == 2

    def test_account_types(self, db, sample_member):
        types = [AccountType.courant, AccountType.livret, AccountType.pea,
                 AccountType.per, AccountType.assurance_vie, AccountType.credit]
        for i, atype in enumerate(types):
            acc = Account(name=f"Compte {i}", type=atype)
            acc.members = [sample_member]
            db.add(acc)
        db.commit()
        assert db.query(Account).count() == len(types)


class TestSeed:
    def test_seed_does_not_create_members(self, seeded_db):
        assert seeded_db.query(FamilyMember).count() == 0

    def test_seed_does_not_create_accounts(self, seeded_db):
        assert seeded_db.query(Account).count() == 0

    def test_seed_creates_categories(self, seeded_db):
        categories = seeded_db.query(Category).all()
        names = {c.name for c in categories}
        assert "Alimentation" in names
        assert "Transport" in names
        assert "Revenus" in names
        assert "Virement interne" in names

    def test_seed_creates_rules(self, seeded_db):
        rules = seeded_db.query(CategoryRule).all()
        assert len(rules) > 0
        user_rules = [r for r in rules if r.source == RuleSource.user]
        assert len(user_rules) == 0  # seed ne crée que des règles auto

    def test_seed_creates_settings(self, seeded_db):
        settings = {s.key: s.value for s in seeded_db.query(Settings).all()}
        assert settings["taux_rendement_annuel"] == "0.05"
        assert settings["surface_maison_m2"] == "0"
        assert settings["valeur_maison_achat"] == "0"

    def test_seed_idempotent(self, seeded_db):
        """Appeler le seed deux fois ne doit pas dupliquer les données."""
        from db.seed import run_seed
        count_before = seeded_db.query(Category).count()
        run_seed(seeded_db)
        count_after = seeded_db.query(Category).count()
        assert count_before == count_after


class TestPatrimonySnapshot:
    def test_create_snapshot(self, db, sample_account):
        snap = PatrimonySnapshot(
            account_id=sample_account.id,
            month="2025-01",
            value=5000.0,
            note="Test",
        )
        db.add(snap)
        db.commit()
        assert snap.id is not None
        assert snap.month == "2025-01"
        assert snap.value == 5000.0

    def test_multiple_months(self, db, sample_account):
        for i, month in enumerate(["2025-01", "2025-02", "2025-03"]):
            db.add(PatrimonySnapshot(
                account_id=sample_account.id,
                month=month,
                value=1000.0 * (i + 1),
            ))
        db.commit()
        snaps = db.query(PatrimonySnapshot).filter_by(account_id=sample_account.id).all()
        assert len(snaps) == 3
