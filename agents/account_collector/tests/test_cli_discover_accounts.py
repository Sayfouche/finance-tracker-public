import json

from account_collector.cli import main


def test_cli_discover_accounts_powens_writes_raw_payload(tmp_path, monkeypatch):
    output = tmp_path / "powens_accounts_raw.json"

    monkeypatch.setenv("AGGREGATOR_BASE_URL", "https://demo.biapi.pro")
    monkeypatch.setenv("AGGREGATOR_ACCESS_TOKEN", "token")
    monkeypatch.setattr(
        "account_collector.connectors.powens.RealPowensProvider.list_accounts_payload",
        lambda self: {"accounts": [{"id": 53185, "name": "Compte Courant Demo A"}]},
    )

    exit_code = main([
        "discover-accounts",
        "--provider", "powens",
        "--output", str(output),
    ])

    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["accounts"][0]["id"] == 53185
