import json
from datetime import date

from fastapi.testclient import TestClient

from api.routes.agents import ApplyDecisionBody, apply_run_decisions
from api.main import app
from core.agent_staging import diff_account_collector_output
from db.database import get_db
from db.models import Account, AccountProviderMapping, AccountType, FamilyMember, MemberRole, Transaction


def _write_snapshot(root, run_id="powens-test"):
    snapshots = root / "snapshots"
    snapshots.mkdir()
    path = snapshots / f"{run_id}.json"
    path.write_text(
        json.dumps({
            "snapshot_date": "2026-05-12T12:00:00+00:00",
            "source": "account_collector",
            "run_id": run_id,
            "accounts": [
                {
                    "external_id": "1",
                    "institution": "Demo Bank B",
                    "account_name": "Compte Demo B",
                    "account_type": "courant",
                    "currency": "EUR",
                    "balance": 100.0,
                    "balance_date": "2026-05-12",
                    "collection_strategy": "powens",
                    "status": "success",
                    "transactions": [
                        {
                            "date": "2026-05-11",
                            "label": "CARREFOUR",
                            "amount": -12.5,
                            "currency": "EUR",
                            "external_id": "tx-1",
                        }
                    ],
                }
            ],
            "errors": [],
        }),
        encoding="utf-8",
    )
    return path


def test_list_agent_runs_from_snapshot_files(tmp_path, monkeypatch):
    _write_snapshot(tmp_path)
    monkeypatch.setenv("ACCOUNT_COLLECTOR_DIR", str(tmp_path))

    client = TestClient(app)
    response = client.get("/agents/account-collector/runs")

    assert response.status_code == 200
    assert response.json()[0]["run_id"] == "powens-test"
    assert response.json()[0]["transactions_count"] == 1


def test_get_agent_run_diff_detects_duplicate_candidate(db, tmp_path, monkeypatch):
    _write_snapshot(tmp_path)
    monkeypatch.setenv("ACCOUNT_COLLECTOR_DIR", str(tmp_path))
    monkeypatch.setattr(
        "api.routes.agents.diff_account_collector_output",
        lambda db, base_dir, run_id: {
            "run_id": run_id,
            "provider": "powens",
            "summary": {"new": 0, "duplicate_candidate": 1, "unmapped_account": 0, "error": 0},
            "items": [],
        },
    )

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.get("/agents/account-collector/runs/powens-test/diff")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["summary"]["duplicate_candidate"] == 1


def test_ignore_agent_run_item_persists_decision(db, tmp_path, monkeypatch):
    _write_snapshot(tmp_path)
    account = _mapped_account(db)

    diff = diff_account_collector_output(db, tmp_path, "powens-test")
    item_id = diff["items"][0]["item_id"]
    monkeypatch.setattr("api.routes.agents._account_collector_dir", lambda: tmp_path)

    response = apply_run_decisions(
        "powens-test",
        ApplyDecisionBody(item_ids=[item_id], decision="ignore"),
        db,
    )
    refreshed = diff_account_collector_output(db, tmp_path, "powens-test")

    assert response["ignored"] == [item_id]
    assert refreshed["items"][0]["decision"] == "ignored"
    assert db.query(Transaction).filter_by(account_id=account.id).count() == 0


def test_import_agent_run_item_creates_transaction_and_external_link(db, tmp_path, monkeypatch):
    _write_snapshot(tmp_path)
    monkeypatch.setattr("api.routes.agents._backup_sqlite_db", lambda: None)
    account = _mapped_account(db)

    diff = diff_account_collector_output(db, tmp_path, "powens-test")
    item_id = diff["items"][0]["item_id"]
    monkeypatch.setattr("api.routes.agents._account_collector_dir", lambda: tmp_path)

    response = apply_run_decisions(
        "powens-test",
        ApplyDecisionBody(item_ids=[item_id], decision="import"),
        db,
    )
    refreshed = diff_account_collector_output(db, tmp_path, "powens-test")

    assert len(response["imported"]) == 1
    tx = db.query(Transaction).filter_by(account_id=account.id).one()
    assert tx.date == date(2026, 5, 11)
    assert tx.amount == 12.5
    assert tx.transaction_type.value == "debit"
    assert refreshed["items"][0]["decision"] == "imported"


def _mapped_account(db):
    member = FamilyMember(first_name="Alex", role=MemberRole.owner)
    db.add(member)
    db.flush()
    account = Account(name="CC", type=AccountType.courant)
    account.members = [member]
    db.add(account)
    db.flush()
    db.add(AccountProviderMapping(
        provider="powens",
        provider_account_id="1",
        local_account_id=account.id,
    ))
    db.commit()
    return account
