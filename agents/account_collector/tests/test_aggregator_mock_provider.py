from pathlib import Path

import pytest

from account_collector.config import AccountConfig
from account_collector.connectors.aggregator_mock import AggregatorMockProvider
from account_collector.models import AccountType


def test_aggregator_mock_provider_maps_provider_payload_to_collected_account():
    fixture = Path(__file__).parents[1] / "fixtures" / "aggregator_mock_accounts.json"
    provider = AggregatorMockProvider(fixture)
    config = AccountConfig(
        external_id="demo-checking-1",
        institution="Demo Bank A",
        account_name="Compte courant Demo A",
        account_type=AccountType.courant,
        preferred_strategy="open_banking",
    )

    account = provider.fetch_account(config)

    assert account.external_id == "demo-checking-1"
    assert account.collection_strategy == "aggregator_mock"
    assert account.balance == 1410.42
    assert account.transactions[0].external_id == "agg-demo-a-tx-001"


def test_aggregator_mock_provider_fails_for_missing_account():
    fixture = Path(__file__).parents[1] / "fixtures" / "aggregator_mock_accounts.json"
    provider = AggregatorMockProvider(fixture)
    config = AccountConfig(
        external_id="missing",
        institution="Demo Bank A",
        account_name="Missing",
        account_type=AccountType.courant,
        preferred_strategy="open_banking",
    )

    with pytest.raises(ValueError, match="account not found"):
        provider.fetch_account(config)
