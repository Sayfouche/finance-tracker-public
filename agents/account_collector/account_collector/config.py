from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import AccountType


@dataclass(frozen=True)
class AccountConfig:
    external_id: str
    institution: str
    account_name: str
    account_type: AccountType
    preferred_strategy: str
    fallback_strategy: str | None = None


@dataclass(frozen=True)
class ProviderCredentials:
    provider: str
    base_url: str | None
    client_id: str | None
    client_secret: str | None
    access_token: str | None

    @classmethod
    def from_env(cls) -> "ProviderCredentials":
        return cls(
            provider=os.getenv("ACCOUNT_COLLECTOR_PROVIDER", "aggregator_mock"),
            base_url=os.getenv("AGGREGATOR_BASE_URL"),
            client_id=os.getenv("AGGREGATOR_CLIENT_ID"),
            client_secret=os.getenv("AGGREGATOR_CLIENT_SECRET"),
            access_token=os.getenv("AGGREGATOR_ACCESS_TOKEN"),
        )


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise ValueError(f"env file does not exist: {path}")

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"invalid env line {line_number}: expected KEY=VALUE")

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid env line {line_number}: empty key")
        os.environ.setdefault(key, _clean_env_value(value.strip()))


def load_account_configs(path: Path) -> list[AccountConfig]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("account config must contain a JSON object")

    accounts = payload.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        raise ValueError("account config must contain at least one account")

    return [_parse_account_config(item) for item in accounts]


def _parse_account_config(data: Any) -> AccountConfig:
    if not isinstance(data, dict):
        raise ValueError("account config entry must be an object")

    return AccountConfig(
        external_id=_required_str(data, "external_id"),
        institution=_required_str(data, "institution"),
        account_name=_required_str(data, "account_name"),
        account_type=AccountType(_required_str(data, "account_type")),
        preferred_strategy=_required_str(data, "preferred_strategy"),
        fallback_strategy=data.get("fallback_strategy"),
    )


def _required_str(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _clean_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
