from pathlib import Path

from account_collector.config import load_account_configs
from account_collector.models import AccountType


def test_load_account_configs():
    path = Path(__file__).parents[1] / "config" / "accounts.example.json"

    configs = load_account_configs(path)

    assert len(configs) == 4
    assert configs[0].external_id == "demo-checking-1"
    assert configs[0].account_type == AccountType.courant
    assert configs[0].preferred_strategy == "open_banking"
    assert configs[0].fallback_strategy == "manual_file"
