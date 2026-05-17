from pathlib import Path

from account_collector.cli import main
from account_collector.snapshot_writer import read_snapshot


def test_cli_collect_writes_snapshot(tmp_path):
    fixture = Path(__file__).parents[1] / "fixtures" / "manual_sample.json"
    output = tmp_path / "latest.json"

    exit_code = main([
        "collect",
        "--provider", "manual_file",
        "--input", str(fixture),
        "--output", str(output),
    ])

    assert exit_code == 0
    assert read_snapshot(output).run_id == "manual-sample-2026-05-12"


def test_cli_validate_accepts_snapshot():
    fixture = Path(__file__).parents[1] / "fixtures" / "manual_sample.json"

    assert main(["validate", str(fixture)]) == 0


def test_cli_collect_open_banking_fake_writes_snapshot(tmp_path):
    config = Path(__file__).parents[1] / "config" / "accounts.example.json"
    output = tmp_path / "open_banking_fake.json"

    exit_code = main([
        "collect",
        "--provider", "open_banking_fake",
        "--config", str(config),
        "--output", str(output),
    ])

    snapshot = read_snapshot(output)
    assert exit_code == 0
    assert len(snapshot.accounts) == 4
    assert {account.collection_strategy for account in snapshot.accounts} == {"open_banking_fake"}


def test_cli_collect_aggregator_mock_writes_snapshot(tmp_path):
    root = Path(__file__).parents[1]
    config = root / "config" / "accounts.example.json"
    fixture = root / "fixtures" / "aggregator_mock_accounts.json"
    output = tmp_path / "aggregator_mock.json"

    exit_code = main([
        "collect",
        "--provider", "aggregator_mock",
        "--config", str(config),
        "--fixture", str(fixture),
        "--output", str(output),
    ])

    snapshot = read_snapshot(output)
    assert exit_code == 0
    assert len(snapshot.accounts) == 4
    assert {account.collection_strategy for account in snapshot.accounts} == {"aggregator_mock"}
    assert snapshot.accounts[0].balance == 1410.42


def test_cli_collect_powens_fixture_writes_snapshot(tmp_path):
    root = Path(__file__).parents[1]
    config = root / "config" / "accounts.example.json"
    fixture = root / "fixtures" / "powens_accounts_transactions.json"
    output = tmp_path / "powens_fixture.json"

    exit_code = main([
        "collect",
        "--provider", "powens_fixture",
        "--config", str(config),
        "--fixture", str(fixture),
        "--output", str(output),
    ])

    snapshot = read_snapshot(output)
    assert exit_code == 0
    assert len(snapshot.accounts) == 4
    assert {account.collection_strategy for account in snapshot.accounts} == {"powens_fixture"}
    assert snapshot.accounts[0].transactions[0].label == "CARREFOUR MARKET"


def test_cli_collect_powens_accepts_date_range(tmp_path, monkeypatch):
    config = Path(__file__).parents[1] / "config" / "accounts.powens.json"
    output = tmp_path / "powens_real.json"
    captured = {}

    class StubProvider:
        name = "powens"

        def __init__(self, credentials, date_from=None, date_to=None):  # noqa: ARG002
            captured["date_from"] = date_from
            captured["date_to"] = date_to

        def fetch_account(self, account_config):
            from datetime import date

            from account_collector.models import CollectedAccount, CollectionStatus

            return CollectedAccount(
                external_id=account_config.external_id,
                institution=account_config.institution,
                account_name=account_config.account_name,
                account_type=account_config.account_type,
                currency="EUR",
                balance=0.0,
                balance_date=date(2026, 5, 12),
                collection_strategy="powens",
                status=CollectionStatus.success,
                transactions=[],
            )

    monkeypatch.setattr("account_collector.cli.RealPowensProvider", StubProvider)

    exit_code = main([
        "collect",
        "--provider", "powens",
        "--config", str(config),
        "--date-from", "2026-01-01",
        "--date-to", "2026-05-13",
        "--output", str(output),
    ])

    assert exit_code == 0
    assert captured["date_from"].isoformat() == "2026-01-01"
    assert captured["date_to"].isoformat() == "2026-05-13"
