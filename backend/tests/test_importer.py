"""Tests de l'import de relevés CSV."""
import os
import tempfile
import pytest
from core.importer import import_transactions, normalize_label
from db.models import Transaction, Account, FamilyMember, Category, CategoryRule, AccountType, MemberRole, RuleMatchType, RuleSource


def _make_account(db):
    m = FamilyMember(first_name="Alex", role=MemberRole.owner)
    db.add(m)
    db.flush()
    acc = Account(name="Compte Demo A", type=AccountType.courant)
    acc.members = [m]
    db.add(acc)
    db.flush()
    return acc


def _make_csv(content: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(content)
        return f.name


class TestImporter:
    def test_basic_import(self, db):
        acc = _make_account(db)
        csv_path = _make_csv(
            "Date;Libellé;Montant\n"
            "15/03/2025;CARREFOUR CITY;-45.30\n"
            "16/03/2025;SALAIRE MARS;+3500.00\n"
        )
        try:
            result = import_transactions(db, acc.id, csv_path)
            assert result["created"] == 2
            assert result["errors"] == 0
            txs = db.query(Transaction).filter_by(account_id=acc.id).all()
            assert len(txs) == 2
        finally:
            os.unlink(csv_path)

    def test_deduplication(self, db):
        acc = _make_account(db)
        csv_content = "Date;Libellé;Montant\n15/03/2025;RATP;-1.90\n"
        csv_path = _make_csv(csv_content)
        try:
            result1 = import_transactions(db, acc.id, csv_path)
            result2 = import_transactions(db, acc.id, csv_path)
            assert result1["created"] == 1
            assert result2["created"] == 0
            assert result2["skipped"] == 1
        finally:
            os.unlink(csv_path)

    def test_debit_credit_columns(self, db):
        acc = _make_account(db)
        csv_path = _make_csv(
            "Date;Libellé;Débit;Crédit\n"
            "01/04/2025;EDF;85.00;\n"
            "02/04/2025;SALAIRE;;3500.00\n"
        )
        try:
            result = import_transactions(db, acc.id, csv_path)
            assert result["created"] == 2
        finally:
            os.unlink(csv_path)

    def test_auto_categorization(self, db):
        acc = _make_account(db)
        cat = Category(name="Alimentation", color="#22c55e", is_system=True)
        db.add(cat)
        db.flush()
        db.add(CategoryRule(
            pattern="carrefour", match_type=RuleMatchType.contains,
            category_id=cat.id, priority=10, source=RuleSource.auto
        ))
        db.commit()

        csv_path = _make_csv("Date;Libellé;Montant\n10/03/2025;CARREFOUR MARKET;-32.50\n")
        try:
            import_transactions(db, acc.id, csv_path)
            tx = db.query(Transaction).filter_by(account_id=acc.id).first()
            assert tx.category_id == cat.id
        finally:
            os.unlink(csv_path)

    def test_invalid_file_returns_error(self, db):
        acc = _make_account(db)
        result = import_transactions(db, acc.id, "/nonexistent/file.csv")
        assert "error" in result

    def test_skips_zero_amount(self, db):
        acc = _make_account(db)
        csv_path = _make_csv("Date;Libellé;Montant\n10/03/2025;ZERO;0.00\n")
        try:
            result = import_transactions(db, acc.id, csv_path)
            assert result["skipped"] == 1
        finally:
            os.unlink(csv_path)
