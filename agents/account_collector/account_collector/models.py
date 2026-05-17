from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class AccountType(str, Enum):
    courant = "courant"
    livret = "livret"
    epargne = "epargne"
    cto = "cto"
    pea = "pea"
    per = "per"
    assurance_vie = "assurance_vie"
    credit = "credit"
    autre = "autre"


class CollectionStatus(str, Enum):
    success = "success"
    partial = "partial"
    failed = "failed"


@dataclass(frozen=True)
class CollectedTransaction:
    date: date
    label: str
    amount: float
    currency: str = "EUR"
    external_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CollectedTransaction":
        return cls(
            date=_parse_date(data["date"], "transaction.date"),
            label=_require_str(data, "label"),
            amount=_require_number(data, "amount"),
            currency=data.get("currency", "EUR"),
            external_id=data.get("external_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "date": self.date.isoformat(),
            "label": self.label,
            "amount": self.amount,
            "currency": self.currency,
        }
        if self.external_id:
            payload["external_id"] = self.external_id
        return payload


@dataclass(frozen=True)
class CollectedAccount:
    external_id: str
    institution: str
    account_name: str
    account_type: AccountType
    currency: str
    balance: float
    balance_date: date
    collection_strategy: str
    status: CollectionStatus = CollectionStatus.success
    transactions: list[CollectedTransaction] = field(default_factory=list)
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CollectedAccount":
        return cls(
            external_id=_require_str(data, "external_id"),
            institution=_require_str(data, "institution"),
            account_name=_require_str(data, "account_name"),
            account_type=AccountType(_require_str(data, "account_type")),
            currency=data.get("currency", "EUR"),
            balance=_require_number(data, "balance"),
            balance_date=_parse_date(data["balance_date"], "balance_date"),
            collection_strategy=_require_str(data, "collection_strategy"),
            status=CollectionStatus(data.get("status", CollectionStatus.success.value)),
            transactions=[
                CollectedTransaction.from_dict(item)
                for item in data.get("transactions", [])
            ],
            error=data.get("error"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "external_id": self.external_id,
            "institution": self.institution,
            "account_name": self.account_name,
            "account_type": self.account_type.value,
            "currency": self.currency,
            "balance": self.balance,
            "balance_date": self.balance_date.isoformat(),
            "collection_strategy": self.collection_strategy,
            "status": self.status.value,
            "transactions": [tx.to_dict() for tx in self.transactions],
        }
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass(frozen=True)
class CollectionSnapshot:
    snapshot_date: datetime
    source: str
    run_id: str
    accounts: list[CollectedAccount]
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CollectionSnapshot":
        accounts = [
            CollectedAccount.from_dict(item)
            for item in data.get("accounts", [])
        ]
        if not accounts:
            raise ValueError("snapshot must contain at least one account")

        return cls(
            snapshot_date=_parse_datetime(data["snapshot_date"], "snapshot_date"),
            source=_require_str(data, "source"),
            run_id=_require_str(data, "run_id"),
            accounts=accounts,
            errors=list(data.get("errors", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_date": self.snapshot_date.isoformat(),
            "source": self.source,
            "run_id": self.run_id,
            "accounts": [account.to_dict() for account in self.accounts],
            "errors": self.errors,
        }


def _require_str(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_number(data: dict[str, Any], field_name: str) -> float:
    value = data.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be a number")
    return float(value)


def _parse_date(value: Any, field_name: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO date string")
    return date.fromisoformat(value)


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO datetime string")
    return datetime.fromisoformat(value)
