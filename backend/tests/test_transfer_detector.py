"""Tests de la détection des virements internes."""
from datetime import date, timedelta
from core.transfer_detector import detect_internal_transfers
from db.models import Transaction, Account, FamilyMember, TransactionType, AccountType, MemberRole


def _make_tx(db, account_id, amount, tx_type, day_offset=0):
    tx = Transaction(
        account_id=account_id,
        date=date(2025, 3, 15) + timedelta(days=day_offset),
        raw_label="TEST", label="test",
        amount=amount,
        transaction_type=tx_type,
        import_hash=f"hash_{account_id}_{amount}_{tx_type}_{day_offset}",
    )
    db.add(tx)
    db.flush()
    return tx


def _make_account(db, name):
    m = FamilyMember(first_name="Test", role=MemberRole.owner)
    db.add(m)
    db.flush()
    acc = Account(name=name, type=AccountType.courant)
    acc.members = [m]
    db.add(acc)
    db.flush()
    return acc


class TestTransferDetector:
    def test_detects_simple_transfer(self, db):
        acc1 = _make_account(db, "Compte Demo A")
        acc2 = _make_account(db, "Livret A")

        tx_out = _make_tx(db, acc1.id, 500.0, TransactionType.debit)
        tx_in  = _make_tx(db, acc2.id, 500.0, TransactionType.credit)
        db.commit()

        count = detect_internal_transfers(db, [tx_out, tx_in])
        assert count == 1
        assert tx_out.is_internal_transfer
        assert tx_in.is_internal_transfer
        assert tx_out.transfer_pair_id == tx_in.id

    def test_detects_within_3_days(self, db):
        acc1 = _make_account(db, "CC")
        acc2 = _make_account(db, "Livret")

        tx_out = _make_tx(db, acc1.id, 300.0, TransactionType.debit, day_offset=0)
        tx_in  = _make_tx(db, acc2.id, 300.0, TransactionType.credit, day_offset=2)
        db.commit()

        count = detect_internal_transfers(db, [tx_out])
        assert count == 1

    def test_no_detection_beyond_3_days(self, db):
        acc1 = _make_account(db, "CC")
        acc2 = _make_account(db, "Livret")

        tx_out = _make_tx(db, acc1.id, 300.0, TransactionType.debit, day_offset=0)
        _make_tx(db, acc2.id, 300.0, TransactionType.credit, day_offset=4)
        db.commit()

        count = detect_internal_transfers(db, [tx_out])
        assert count == 0

    def test_no_detection_different_amounts(self, db):
        acc1 = _make_account(db, "CC")
        acc2 = _make_account(db, "Livret")

        tx_out = _make_tx(db, acc1.id, 300.0, TransactionType.debit)
        _make_tx(db, acc2.id, 400.0, TransactionType.credit)
        db.commit()

        count = detect_internal_transfers(db, [tx_out])
        assert count == 0

    def test_no_detection_same_account(self, db):
        acc = _make_account(db, "CC")
        tx1 = _make_tx(db, acc.id, 200.0, TransactionType.debit)
        _make_tx(db, acc.id, 200.0, TransactionType.credit)
        db.commit()

        count = detect_internal_transfers(db, [tx1])
        assert count == 0
