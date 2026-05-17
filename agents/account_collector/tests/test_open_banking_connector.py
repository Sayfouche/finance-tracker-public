from account_collector.config import AccountConfig
from account_collector.connectors.open_banking import FakeOpenBankingProvider, OpenBankingConnector
from account_collector.models import AccountType, CollectionStatus


def test_open_banking_fake_collects_configured_accounts():
    configs = [
        AccountConfig(
            external_id="demo-checking-1",
            institution="Demo Bank A",
            account_name="Compte courant Demo A",
            account_type=AccountType.courant,
            preferred_strategy="open_banking",
        ),
        AccountConfig(
            external_id="demo-checking-2",
            institution="Demo Bank B",
            account_name="Compte courant Demo B",
            account_type=AccountType.courant,
            preferred_strategy="open_banking",
        ),
    ]

    snapshot = OpenBankingConnector(FakeOpenBankingProvider(), configs, run_id="test").collect()

    assert snapshot.run_id == "test"
    assert snapshot.errors == []
    assert [account.external_id for account in snapshot.accounts] == [
        "demo-checking-1",
        "demo-checking-2",
    ]
    assert snapshot.accounts[0].collection_strategy == "open_banking_fake"
    assert snapshot.accounts[0].transactions[0].label == "CARREFOUR"


def test_open_banking_fake_isolates_account_errors():
    configs = [
        AccountConfig(
            external_id="unknown-account",
            institution="Unknown",
            account_name="Unknown",
            account_type=AccountType.courant,
            preferred_strategy="open_banking",
        )
    ]

    snapshot = OpenBankingConnector(FakeOpenBankingProvider(), configs, run_id="test").collect()

    assert len(snapshot.errors) == 1
    assert snapshot.accounts[0].status == CollectionStatus.failed
    assert snapshot.accounts[0].error == "no fake data configured"
