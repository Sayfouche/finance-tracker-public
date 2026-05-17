import json

from account_collector.cli import main


def test_cli_init_user_writes_powens_token_response(tmp_path, monkeypatch):
    output = tmp_path / "powens_user.json"

    monkeypatch.setenv("AGGREGATOR_BASE_URL", "https://demo.biapi.pro")
    monkeypatch.setenv("AGGREGATOR_CLIENT_ID", "client-id")
    monkeypatch.setenv("AGGREGATOR_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(
        "account_collector.connectors.powens.RealPowensProvider.init_user_token",
        lambda credentials: {"auth_token": "token", "type": "permanent", "id_user": 42},
    )

    exit_code = main([
        "init-user",
        "--provider", "powens",
        "--output", str(output),
    ])

    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["auth_token"] == "token"


def test_cli_create_webview_url_writes_connect_url(tmp_path, monkeypatch):
    output = tmp_path / "powens_connect_url.txt"

    monkeypatch.setenv("AGGREGATOR_BASE_URL", "https://demo.biapi.pro")
    monkeypatch.setenv("AGGREGATOR_CLIENT_ID", "client-id")
    monkeypatch.setenv("AGGREGATOR_ACCESS_TOKEN", "token")
    monkeypatch.setattr(
        "account_collector.connectors.powens.RealPowensProvider.generate_temporary_code",
        lambda self: {"code": "temporary-code"},
    )

    exit_code = main([
        "create-webview-url",
        "--provider", "powens",
        "--redirect-uri", "http://localhost:3000/powens/callback",
        "--output", str(output),
    ])

    url = output.read_text(encoding="utf-8")
    assert exit_code == 0
    assert "https://webview.powens.com/fr/connect?" in url
    assert "domain=demo.biapi.pro" in url
    assert "client_id=client-id" in url
    assert "code=temporary-code" in url
