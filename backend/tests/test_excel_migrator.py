"""Tests du module de migration Excel."""
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch, MagicMock
from core.excel_migrator import _parse_month, migrate_sheet, migrate_pret_immo, run_migration
from db.models import PatrimonySnapshot, Account, AccountType, AccountStatus, FamilyMember, MemberRole


class TestParseMonth:
    def test_datetime_object(self):
        dt = datetime(2025, 1, 5)
        assert _parse_month(dt) == "2025-01"

    def test_string_date(self):
        assert _parse_month("2025-03-10") == "2025-03"

    def test_pandas_timestamp(self):
        ts = pd.Timestamp("2025-06-01")
        assert _parse_month(ts) == "2025-06"

    def test_none_returns_none(self):
        assert _parse_month(None) is None

    def test_invalid_returns_none(self):
        assert _parse_month("not-a-date") is None


class TestMigrateSheet:
    def _make_account(self, db, name):
        m = FamilyMember(first_name="Alex", role=MemberRole.owner)
        db.add(m)
        db.flush()
        acc = Account(name=name, type=AccountType.courant, status=AccountStatus.actif)
        acc.members = [m]
        db.add(acc)
        db.flush()
        return acc

    def test_basic_migration(self, db):
        self._make_account(db, "Compte Demo A")

        df = pd.DataFrame({
            "Date": [datetime(2025, 1, 5), datetime(2025, 2, 5)],
            "Compte Demo A": [6087.0, 2780.0],
        })

        count = migrate_sheet(db, df, [("Compte Demo A", "Compte Demo A")])
        assert count == 2

        snaps = db.query(PatrimonySnapshot).all()
        assert len(snaps) == 2
        months = {s.month for s in snaps}
        assert "2025-01" in months
        assert "2025-02" in months

    def test_skips_missing_column(self, db):
        df = pd.DataFrame({
            "Date": [datetime(2025, 1, 5)],
            "Autre col": [100.0],
        })
        count = migrate_sheet(db, df, [("Compte Demo A", "Compte Demo A")])
        assert count == 0

    def test_skips_null_values(self, db):
        self._make_account(db, "Compte Demo A")
        df = pd.DataFrame({
            "Date": [datetime(2025, 1, 5), datetime(2025, 2, 5)],
            "Compte Demo A": [None, 2780.0],
        })
        count = migrate_sheet(db, df, [("Compte Demo A", "Compte Demo A")])
        assert count == 1

    def test_updates_existing_snapshot(self, db):
        acc = self._make_account(db, "Compte Demo A")
        db.add(PatrimonySnapshot(account_id=acc.id, month="2025-01", value=1000.0))
        db.commit()

        df = pd.DataFrame({
            "Date": [datetime(2025, 1, 5)],
            "Compte Demo A": [6087.0],
        })
        count = migrate_sheet(db, df, [("Compte Demo A", "Compte Demo A")])
        assert count == 0  # pas de création, mise à jour

        snap = db.query(PatrimonySnapshot).filter_by(account_id=acc.id, month="2025-01").first()
        assert snap.value == 6087.0

    def test_skips_unknown_account(self, db):
        df = pd.DataFrame({
            "Date": [datetime(2025, 1, 5)],
            "Compte Demo A": [6087.0],
        })
        count = migrate_sheet(db, df, [("Compte Demo A", "Compte Inexistant")])
        assert count == 0


class TestMigratePretImmo:
    def test_basic_pret_migration(self, db):
        m = FamilyMember(first_name="Alex", role=MemberRole.owner)
        db.add(m)
        db.flush()
        pret = Account(name="Prêt immo", type=AccountType.credit, status=AccountStatus.actif)
        pret.members = [m]
        db.add(pret)
        db.flush()

        df = pd.DataFrame({
            "Échéance": [datetime(2025, 4, 5), datetime(2025, 5, 5)],
            "Restant dû": [471617.38, 470586.10],
        })

        count = migrate_pret_immo(db, df)
        assert count == 2

        snaps = db.query(PatrimonySnapshot).filter_by(account_id=pret.id).all()
        assert all(s.value < 0 for s in snaps)  # passif = négatif

    def test_no_pret_immo_account(self, db):
        df = pd.DataFrame({
            "Échéance": [datetime(2025, 4, 5)],
            "Restant dû": [471617.38],
        })
        count = migrate_pret_immo(db, df)
        assert count == 0


class TestRunMigration:
    def test_invalid_file(self, db):
        result = run_migration(db, "/chemin/inexistant.xlsx")
        assert "error" in result

    def test_with_real_excel(self, seeded_db):
        """Test d'intégration avec le vrai fichier Excel."""
        import os
        excel_path = "/tmp/demo_patrimony_template.xlsx"
        if not os.path.exists(excel_path):
            pytest.skip("Fichier Excel non disponible")

        result = run_migration(seeded_db, excel_path)
        assert "error" not in result

        # Au moins quelques snapshots créés
        total = seeded_db.query(PatrimonySnapshot).count()
        assert total > 0
