from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

from account_collector.config import AccountConfig, ProviderCredentials
from account_collector.connectors.open_banking import OpenBankingProvider
from account_collector.models import CollectedAccount, CollectedTransaction, CollectionStatus


POWENS_WEBVIEW_BASE_URL = "https://webview.powens.com"


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


class PowensFixtureProvider(OpenBankingProvider):
    name = "powens_fixture"

    def __init__(self, fixture_path: Path):
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        self._accounts = _index_accounts(payload)
        self._transactions = _index_transactions(payload)

    def fetch_account(self, account: AccountConfig) -> CollectedAccount:
        raw_account = self._accounts.get(account.external_id)
        if raw_account is None:
            raise ValueError("account not found in Powens fixture")

        currency = _currency(raw_account)
        return CollectedAccount(
            external_id=account.external_id,
            institution=account.institution,
            account_name=account.account_name,
            account_type=account.account_type,
            currency=currency,
            balance=_number(raw_account, "balance"),
            balance_date=_parse_powens_datetime(raw_account.get("last_update")),
            collection_strategy=self.name,
            status=CollectionStatus.success,
            transactions=[
                _map_transaction(tx, currency)
                for tx in self._transactions.get(str(raw_account["id"]), [])
            ],
        )


class RealPowensProvider(OpenBankingProvider):
    name = "powens"

    def __init__(
        self,
        credentials: ProviderCredentials,
        transaction_limit: int = 1000,
        date_from: date | None = None,
        date_to: date | None = None,
        timeout_seconds: float = 20.0,
    ):
        if not credentials.base_url:
            raise ValueError("AGGREGATOR_BASE_URL is required for provider powens")
        if not credentials.access_token:
            raise ValueError("AGGREGATOR_ACCESS_TOKEN is required for provider powens")

        self.client_id = credentials.client_id
        self.client_secret = credentials.client_secret
        self.base_url = credentials.base_url.rstrip("/")
        self.access_token = credentials.access_token
        self.transaction_limit = transaction_limit
        self.date_from = date_from
        self.date_to = date_to
        self.timeout_seconds = timeout_seconds
        self._accounts: dict[str, dict[str, Any]] | None = None
        self._transactions: dict[str, list[dict[str, Any]]] = {}

    def list_accounts_payload(self) -> dict[str, Any]:
        return self._request_json("/users/me/accounts")

    def generate_temporary_code(self, code_type: str = "singleAccess") -> dict[str, Any]:
        query = urllib.parse.urlencode({"type": code_type})
        return self._request_json(f"/auth/token/code?{query}")

    def connect_webview_url(
        self,
        redirect_uri: str,
        code: str,
        lang: str = "fr",
        state: str | None = None,
    ) -> str:
        if not self.client_id:
            raise ValueError("AGGREGATOR_CLIENT_ID is required to build the Powens webview URL")

        query: dict[str, str] = {
            "domain": urllib.parse.urlparse(self.base_url).netloc,
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "code": code,
            "connector_capabilities": "bank",
        }
        if state:
            query["state"] = state
        return f"{POWENS_WEBVIEW_BASE_URL}/{lang}/connect?{urllib.parse.urlencode(query)}"

    @classmethod
    def init_user_token(
        cls,
        credentials: ProviderCredentials,
        timeout_seconds: float = 20.0,
    ) -> dict[str, Any]:
        if not credentials.base_url:
            raise ValueError("AGGREGATOR_BASE_URL is required for provider powens")
        if not credentials.client_id:
            raise ValueError("AGGREGATOR_CLIENT_ID is required for provider powens")
        if not credentials.client_secret:
            raise ValueError("AGGREGATOR_CLIENT_SECRET is required for provider powens")

        request = urllib.request.Request(
            f"{credentials.base_url.rstrip('/')}/2.0/auth/init",
            data=json.dumps({
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
            }).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
                context=_ssl_context(),
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Powens API HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Powens API request failed: {exc.reason}") from exc

        if not isinstance(payload, dict):
            raise ValueError("Powens API response must be a JSON object")
        return payload

    def fetch_account(self, account: AccountConfig) -> CollectedAccount:
        raw_account = self._load_accounts().get(account.external_id)
        if raw_account is None:
            raise ValueError("account not found in Powens API response")

        powens_account_id = str(raw_account["id"])
        currency = _currency(raw_account)
        return CollectedAccount(
            external_id=account.external_id,
            institution=account.institution,
            account_name=account.account_name,
            account_type=account.account_type,
            currency=currency,
            balance=_number(raw_account, "balance"),
            balance_date=_parse_powens_datetime(raw_account.get("last_update")),
            collection_strategy=self.name,
            status=CollectionStatus.success,
            transactions=[
                _map_transaction(tx, currency)
                for tx in self._load_transactions(powens_account_id)
            ],
        )

    def _load_accounts(self) -> dict[str, dict[str, Any]]:
        if self._accounts is not None:
            return self._accounts

        payload = self._request_json("/users/me/accounts")
        self._accounts = _index_accounts(payload)
        return self._accounts

    def _load_transactions(self, powens_account_id: str) -> list[dict[str, Any]]:
        if powens_account_id not in self._transactions:
            query_params: dict[str, str | int] = {
                "limit": self.transaction_limit,
                "filter": "date",
            }
            if self.date_from is not None:
                query_params["min_date"] = self.date_from.isoformat()
            if self.date_to is not None:
                query_params["max_date"] = self.date_to.isoformat()
            query = urllib.parse.urlencode(query_params)
            payload = self._request_json(
                f"/users/me/accounts/{powens_account_id}/transactions?{query}"
            )
            transactions = payload.get("transactions", [])
            if not isinstance(transactions, list):
                raise ValueError("Powens transactions response must contain a list")
            self._transactions[powens_account_id] = transactions
        return self._transactions[powens_account_id]

    def _request_json(self, path: str) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/2.0{path}",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
                context=_ssl_context(),
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Powens API HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Powens API request failed: {exc.reason}") from exc

        if not isinstance(payload, dict):
            raise ValueError("Powens API response must be a JSON object")
        return payload


def _index_accounts(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    accounts = payload.get("accounts")
    if not isinstance(accounts, list):
        raise ValueError("Powens fixture must contain an accounts list")

    indexed: dict[str, dict[str, Any]] = {}
    for account in accounts:
        if not isinstance(account, dict):
            raise ValueError("Powens account entries must be objects")
        external_id = _external_id(account)
        indexed[external_id] = account
    return indexed


def _external_id(account: dict[str, Any]) -> str:
    configured_id = account.get("external_id")
    if isinstance(configured_id, str) and configured_id:
        return configured_id

    account_id = account.get("id")
    if account_id is None:
        raise ValueError("Powens account missing id")
    return str(account_id)


def _index_transactions(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    transactions = payload.get("transactions", [])
    if not isinstance(transactions, list):
        raise ValueError("Powens fixture transactions must be a list")

    indexed: dict[str, list[dict[str, Any]]] = {}
    for transaction in transactions:
        if not isinstance(transaction, dict):
            raise ValueError("Powens transaction entries must be objects")
        account_id = transaction.get("id_account")
        if account_id is None:
            raise ValueError("Powens transaction missing id_account")
        indexed.setdefault(str(account_id), []).append(transaction)
    return indexed


def _map_transaction(raw: dict[str, Any], fallback_currency: str) -> CollectedTransaction:
    return CollectedTransaction(
        date=_parse_powens_date(raw.get("date")),
        label=_transaction_label(raw),
        amount=_number(raw, "value"),
        currency=_currency(raw, fallback_currency),
        external_id=str(raw["id"]),
    )


def _transaction_label(raw: dict[str, Any]) -> str:
    for field_name in ("wording", "raw", "simplified_wording"):
        value = raw.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError("Powens transaction missing label")


def _currency(raw: dict[str, Any], fallback: str = "EUR") -> str:
    currency = raw.get("currency")
    if isinstance(currency, dict):
        currency_id = currency.get("id")
        if isinstance(currency_id, str) and currency_id:
            return currency_id
    if isinstance(currency, str) and currency:
        return currency
    return fallback


def _number(raw: dict[str, Any], field_name: str) -> float:
    value = raw.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"Powens field {field_name} must be a number")
    return float(value)


def _parse_powens_datetime(value: Any) -> date:
    if not isinstance(value, str) or not value:
        raise ValueError("Powens last_update must be a date string")
    return datetime.fromisoformat(value.replace(" ", "T")).date()


def _parse_powens_date(value: Any) -> date:
    if not isinstance(value, str) or not value:
        raise ValueError("Powens transaction date must be a date string")
    return date.fromisoformat(value[:10])
