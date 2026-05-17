from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, date, datetime

from account_collector.config import AccountConfig
from account_collector.connectors.base import AccountConnector
from account_collector.models import (
    CollectedAccount,
    CollectedTransaction,
    CollectionSnapshot,
    CollectionStatus,
)
from account_collector.normalizer import normalize_snapshot


class OpenBankingProvider(ABC):
    name: str

    @abstractmethod
    def fetch_account(self, account: AccountConfig) -> CollectedAccount:
        """Fetch one account from the provider."""


class OpenBankingConnector(AccountConnector):
    name = "open_banking"

    def __init__(
        self,
        provider: OpenBankingProvider,
        account_configs: list[AccountConfig],
        run_id: str | None = None,
    ):
        self.provider = provider
        self.account_configs = account_configs
        self.run_id = run_id

    def collect(self) -> CollectionSnapshot:
        accounts: list[CollectedAccount] = []
        errors: list[str] = []

        for account_config in self.account_configs:
            try:
                accounts.append(self.provider.fetch_account(account_config))
            except Exception as exc:  # noqa: BLE001 - isolate account-level failures
                errors.append(f"{account_config.external_id}: {exc}")
                accounts.append(
                    CollectedAccount(
                        external_id=account_config.external_id,
                        institution=account_config.institution,
                        account_name=account_config.account_name,
                        account_type=account_config.account_type,
                        currency="EUR",
                        balance=0.0,
                        balance_date=date.today(),
                        collection_strategy=self.provider.name,
                        status=CollectionStatus.failed,
                        transactions=[],
                        error=str(exc),
                    )
                )

        snapshot = CollectionSnapshot(
            snapshot_date=datetime.now(UTC),
            source="account_collector",
            run_id=self.run_id or f"{self.provider.name}-{date.today().isoformat()}",
            accounts=accounts,
            errors=errors,
        )
        return normalize_snapshot(snapshot)


class FakeOpenBankingProvider(OpenBankingProvider):
    name = "open_banking_fake"

    def fetch_account(self, account: AccountConfig) -> CollectedAccount:
        fixture = _FAKE_BALANCES.get(account.external_id)
        if fixture is None:
            raise ValueError("no fake data configured")

        return CollectedAccount(
            external_id=account.external_id,
            institution=account.institution,
            account_name=account.account_name,
            account_type=account.account_type,
            currency="EUR",
            balance=fixture["balance"],
            balance_date=date.fromisoformat(fixture["balance_date"]),
            collection_strategy=self.name,
            status=CollectionStatus.success,
            transactions=[
                CollectedTransaction(
                    date=date.fromisoformat(tx["date"]),
                    label=tx["label"],
                    amount=tx["amount"],
                    currency="EUR",
                    external_id=tx.get("external_id"),
                )
                for tx in fixture.get("transactions", [])
            ],
        )


_FAKE_BALANCES = {
    "demo-checking-1": {
        "balance": 1320.42,
        "balance_date": "2026-05-12",
        "transactions": [
            {
                "date": "2026-05-11",
                "label": "CARREFOUR",
                "amount": -51.20,
                "external_id": "fake-demo-a-001",
            }
        ],
    },
    "demo-savings-1": {
        "balance": 8050.0,
        "balance_date": "2026-05-12",
        "transactions": [],
    },
    "demo-savings-2": {
        "balance": 12000.0,
        "balance_date": "2026-05-12",
        "transactions": [],
    },
    "demo-checking-2": {
        "balance": 610.15,
        "balance_date": "2026-05-12",
        "transactions": [
            {
                "date": "2026-05-10",
                "label": "VIREMENT INTERNE DEMO",
                "amount": 500.0,
                "external_id": "fake-demo-b-001",
            }
        ],
    },
}
