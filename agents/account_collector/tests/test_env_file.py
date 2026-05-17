import os

import pytest

from account_collector.config import ProviderCredentials, load_env_file


def test_load_env_file_sets_missing_environment_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join([
            "AGGREGATOR_BASE_URL=https://demo-sandbox.biapi.pro",
            'AGGREGATOR_CLIENT_ID="client-id"',
            "AGGREGATOR_CLIENT_SECRET='client-secret'",
            "AGGREGATOR_ACCESS_TOKEN=token",
        ]),
        encoding="utf-8",
    )
    monkeypatch.delenv("AGGREGATOR_BASE_URL", raising=False)
    monkeypatch.delenv("AGGREGATOR_CLIENT_ID", raising=False)
    monkeypatch.delenv("AGGREGATOR_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("AGGREGATOR_ACCESS_TOKEN", raising=False)

    load_env_file(env_file)

    credentials = ProviderCredentials.from_env()
    assert credentials.base_url == "https://demo-sandbox.biapi.pro"
    assert credentials.client_id == "client-id"
    assert credentials.client_secret == "client-secret"
    assert credentials.access_token == "token"


def test_load_env_file_does_not_override_existing_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("AGGREGATOR_ACCESS_TOKEN=file-token", encoding="utf-8")
    monkeypatch.setenv("AGGREGATOR_ACCESS_TOKEN", "shell-token")

    load_env_file(env_file)

    assert os.environ["AGGREGATOR_ACCESS_TOKEN"] == "shell-token"


def test_load_env_file_rejects_invalid_line(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("INVALID", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid env line"):
        load_env_file(env_file)
