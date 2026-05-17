from datetime import date
from pathlib import Path
from urllib.error import URLError

import pytest

from account_collector.config import AccountConfig, ProviderCredentials
from account_collector.connectors.powens import PowensFixtureProvider, RealPowensProvider
from account_collector.models import AccountType


def test_powens_fixture_provider_maps_accounts_and_transactions():
    fixture = Path(__file__).parents[1] / "fixtures" / "powens_accounts_transactions.json"
    provider = PowensFixtureProvider(fixture)
    config = AccountConfig(
        external_id="demo-checking-1",
        institution="Demo Bank A",
        account_name="Compte courant Demo A",
        account_type=AccountType.courant,
        preferred_strategy="open_banking",
    )

    account = provider.fetch_account(config)

    assert account.external_id == "demo-checking-1"
    assert account.institution == "Demo Bank A"
    assert account.collection_strategy == "powens_fixture"
    assert account.currency == "EUR"
    assert account.balance == 1410.42
    assert account.balance_date.isoformat() == "2026-05-12"
    assert [tx.external_id for tx in account.transactions] == ["900001", "900002"]
    assert account.transactions[0].label == "CARREFOUR MARKET"
    assert account.transactions[0].amount == -51.2


def test_powens_fixture_provider_handles_savings_without_transactions():
    fixture = Path(__file__).parents[1] / "fixtures" / "powens_accounts_transactions.json"
    provider = PowensFixtureProvider(fixture)
    config = AccountConfig(
        external_id="demo-savings-1",
        institution="Demo Bank A",
        account_name="Livret Demo A",
        account_type=AccountType.livret,
        preferred_strategy="open_banking",
    )

    account = provider.fetch_account(config)

    assert account.account_type == AccountType.livret
    assert account.balance == 8050.0
    assert account.transactions == []


def test_powens_fixture_provider_fails_for_missing_account():
    fixture = Path(__file__).parents[1] / "fixtures" / "powens_accounts_transactions.json"
    provider = PowensFixtureProvider(fixture)
    config = AccountConfig(
        external_id="missing",
        institution="Demo Bank A",
        account_name="Missing",
        account_type=AccountType.courant,
        preferred_strategy="open_banking",
    )

    with pytest.raises(ValueError, match="account not found"):
        provider.fetch_account(config)


def test_real_powens_provider_requires_base_url():
    credentials = ProviderCredentials(
        provider="powens",
        base_url=None,
        client_id=None,
        client_secret=None,
        access_token="token",
    )

    with pytest.raises(ValueError, match="AGGREGATOR_BASE_URL"):
        RealPowensProvider(credentials)


def test_real_powens_provider_requires_access_token():
    credentials = ProviderCredentials(
        provider="powens",
        base_url="https://demo.biapi.pro",
        client_id=None,
        client_secret=None,
        access_token=None,
    )

    with pytest.raises(ValueError, match="AGGREGATOR_ACCESS_TOKEN"):
        RealPowensProvider(credentials)


def test_real_powens_provider_maps_api_responses(monkeypatch):
    responses = {
        "https://demo.biapi.pro/2.0/users/me/accounts": {
            "accounts": [
                {
                    "id": 53185,
                    "name": "Compte Courant Demo A",
                    "balance": 1410.42,
                    "last_update": "2026-05-12 08:15:41",
                    "currency": {"id": "EUR"},
                }
            ]
        },
        "https://demo.biapi.pro/2.0/users/me/accounts/53185/transactions?limit=1000&filter=date": {
            "transactions": [
                {
                    "id": 900001,
                    "id_account": 53185,
                    "date": "2026-05-11",
                    "value": -51.2,
                    "wording": "CARREFOUR MARKET",
                    "currency": {"id": "EUR"},
                }
            ]
        },
    }

    def fake_urlopen(request, **kwargs):  # noqa: ARG001
        return _FakeResponse(responses[request.full_url])

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = RealPowensProvider(
        ProviderCredentials(
            provider="powens",
            base_url="https://demo.biapi.pro",
            client_id=None,
            client_secret=None,
            access_token="token",
        )
    )
    config = AccountConfig(
        external_id="53185",
        institution="Demo Bank A",
        account_name="Compte courant Demo A",
        account_type=AccountType.courant,
        preferred_strategy="open_banking",
    )

    account = provider.fetch_account(config)

    assert account.collection_strategy == "powens"
    assert account.balance == 1410.42
    assert account.transactions[0].external_id == "900001"
    assert account.transactions[0].label == "CARREFOUR MARKET"


def test_real_powens_provider_filters_transactions_by_date_range(monkeypatch):
    requested_urls = []
    responses = {
        "https://demo.biapi.pro/2.0/users/me/accounts": {
            "accounts": [
                {
                    "id": 53185,
                    "name": "Compte Courant Demo A",
                    "balance": 1410.42,
                    "last_update": "2026-05-12 08:15:41",
                    "currency": {"id": "EUR"},
                }
            ]
        },
        "https://demo.biapi.pro/2.0/users/me/accounts/53185/transactions?limit=1000&filter=date&min_date=2026-01-01&max_date=2026-05-13": {
            "transactions": []
        },
    }

    def fake_urlopen(request, **kwargs):  # noqa: ARG001
        requested_urls.append(request.full_url)
        return _FakeResponse(responses[request.full_url])

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = RealPowensProvider(
        ProviderCredentials(
            provider="powens",
            base_url="https://demo.biapi.pro",
            client_id=None,
            client_secret=None,
            access_token="token",
        ),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 5, 13),
    )
    config = AccountConfig(
        external_id="53185",
        institution="Demo Bank A",
        account_name="Compte courant Demo A",
        account_type=AccountType.courant,
        preferred_strategy="open_banking",
    )

    account = provider.fetch_account(config)

    assert account.transactions == []
    assert requested_urls[-1].endswith(
        "/transactions?limit=1000&filter=date&min_date=2026-01-01&max_date=2026-05-13"
    )


def test_real_powens_provider_lists_accounts_payload(monkeypatch):
    payload = {"accounts": [{"id": 53185, "balance": 1410.42}]}

    def fake_urlopen(request, **kwargs):  # noqa: ARG001
        assert request.full_url == "https://demo.biapi.pro/2.0/users/me/accounts"
        return _FakeResponse(payload)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = RealPowensProvider(
        ProviderCredentials(
            provider="powens",
            base_url="https://demo.biapi.pro",
            client_id=None,
            client_secret=None,
            access_token="token",
        )
    )

    assert provider.list_accounts_payload() == payload


def test_real_powens_provider_wraps_network_errors(monkeypatch):
    def fake_urlopen(request, **kwargs):  # noqa: ARG001
        raise URLError("offline")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = RealPowensProvider(
        ProviderCredentials(
            provider="powens",
            base_url="https://demo.biapi.pro",
            client_id=None,
            client_secret=None,
            access_token="token",
        )
    )
    config = AccountConfig(
        external_id="53185",
        institution="Demo Bank A",
        account_name="Compte courant Demo A",
        account_type=AccountType.courant,
        preferred_strategy="open_banking",
    )

    with pytest.raises(RuntimeError, match="Powens API request failed"):
        provider.fetch_account(config)


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def read(self):
        import json

        return json.dumps(self.payload).encode("utf-8")
