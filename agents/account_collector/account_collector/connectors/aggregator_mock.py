from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from account_collector.config import AccountConfig
from account_collector.connectors.open_banking import OpenBankingProvider
from account_collector.models import CollectedAccount, CollectedTransaction, CollectionStatus


class AggregatorMockProvider(OpenBankingProvider):
    name = "aggregator_mock"

    def __init__(self, fixture_path: Path):
        self.fixture_path = fixture_path
        self._accounts = self._load_accounts(fixture_path)

    def fetch_account(self, account: AccountConfig) -> CollectedAccount:
        raw = self._accounts.get(account.external_id)
        if raw is None:
            raise ValueError("account not found in aggregator response")

        return CollectedAccount(
            external_id=account.external_id,
            institution=account.institution,
            account_name=account.account_name,
            account_type=account.account_type,
            currency=raw.get("currency", "EUR"),
            balance=float(raw["balance"]),
            balance_date=date.fromisoformat(raw["balance_date"]),
            collection_strategy=self.name,
            status=CollectionStatus.success,
            transactions=[
                CollectedTransaction(
                    date=date.fromisoformat(tx["date"]),
                    label=tx["label"],
                    amount=float(tx["amount"]),
                    currency=raw.get("currency", "EUR"),
                    external_id=tx.get("id"),
                )
                for tx in raw.get("transactions", [])
            ],
        )

    @staticmethod
    def _load_accounts(path: Path) -> dict[str, dict[str, Any]]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        accounts = payload.get("accounts")
        if not isinstance(accounts, list):
            raise ValueError("aggregator fixture must contain accounts list")

        loaded: dict[str, dict[str, Any]] = {}
        for account in accounts:
            if not isinstance(account, dict):
                raise ValueError("aggregator account entries must be objects")
            external_id = account.get("external_id")
            if not isinstance(external_id, str) or not external_id:
                raise ValueError("aggregator account missing external_id")
            loaded[external_id] = account
        return loaded
