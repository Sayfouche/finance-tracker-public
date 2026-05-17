from pathlib import Path

from account_collector.connectors.manual_file import ManualFileConnector


def test_manual_file_connector_reads_and_normalizes_fixture():
    fixture = Path(__file__).parents[1] / "fixtures" / "manual_sample.json"

    snapshot = ManualFileConnector(fixture).collect()

    assert snapshot.run_id == "manual-sample-2026-05-12"
    assert [account.external_id for account in snapshot.accounts] == [
        "demo-checking-1",
        "demo-savings-1",
        "demo-savings-2",
        "demo-checking-2",
    ]
    assert sum(account.balance for account in snapshot.accounts) == 21790.57
