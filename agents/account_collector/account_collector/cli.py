from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from account_collector.config import ProviderCredentials, load_account_configs, load_env_file
from account_collector.connectors.aggregator_mock import AggregatorMockProvider
from account_collector.connectors.manual_file import ManualFileConnector
from account_collector.connectors.open_banking import (
    FakeOpenBankingProvider,
    OpenBankingConnector,
)
from account_collector.connectors.powens import PowensFixtureProvider, RealPowensProvider
from account_collector.snapshot_writer import read_snapshot, write_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="account_collector")
    parser.add_argument("--env-file", type=Path, help="Load provider secrets from a local .env file")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="Collect accounts from a provider")
    collect.add_argument(
        "--provider",
        required=True,
        choices=["manual_file", "open_banking_fake", "aggregator_mock", "powens_fixture", "powens"],
    )
    collect.add_argument("--input", type=Path)
    collect.add_argument("--config", type=Path)
    collect.add_argument("--fixture", type=Path)
    collect.add_argument("--date-from", type=date.fromisoformat)
    collect.add_argument("--date-to", type=date.fromisoformat)
    collect.add_argument("--output", required=True, type=Path)

    validate = subparsers.add_parser("validate", help="Validate a snapshot JSON file")
    validate.add_argument("snapshot", type=Path)

    discover = subparsers.add_parser("discover-accounts", help="List raw accounts from a provider")
    discover.add_argument("--provider", required=True, choices=["powens"])
    discover.add_argument("--output", required=True, type=Path)

    init_user = subparsers.add_parser("init-user", help="Create a Powens user token")
    init_user.add_argument("--provider", required=True, choices=["powens"])
    init_user.add_argument("--output", required=True, type=Path)

    webview = subparsers.add_parser("create-webview-url", help="Create a Powens Connect webview URL")
    webview.add_argument("--provider", required=True, choices=["powens"])
    webview.add_argument("--redirect-uri", required=True)
    webview.add_argument("--state")
    webview.add_argument("--output", required=True, type=Path)

    args = parser.parse_args(argv)

    if args.env_file is not None:
        load_env_file(args.env_file)

    if args.command == "collect":
        if args.provider == "manual_file":
            if args.input is None:
                parser.error("--input is required for provider manual_file")
            connector = ManualFileConnector(args.input)
        elif args.provider == "open_banking_fake":
            if args.config is None:
                parser.error("--config is required for provider open_banking_fake")
            connector = OpenBankingConnector(
                provider=FakeOpenBankingProvider(),
                account_configs=load_account_configs(args.config),
            )
        elif args.provider == "aggregator_mock":
            if args.config is None:
                parser.error("--config is required for provider aggregator_mock")
            if args.fixture is None:
                parser.error("--fixture is required for provider aggregator_mock")
            connector = OpenBankingConnector(
                provider=AggregatorMockProvider(args.fixture),
                account_configs=load_account_configs(args.config),
            )
        elif args.provider == "powens_fixture":
            if args.config is None:
                parser.error("--config is required for provider powens_fixture")
            if args.fixture is None:
                parser.error("--fixture is required for provider powens_fixture")
            connector = OpenBankingConnector(
                provider=PowensFixtureProvider(args.fixture),
                account_configs=load_account_configs(args.config),
            )
        else:
            if args.config is None:
                parser.error("--config is required for provider powens")
            connector = OpenBankingConnector(
                provider=RealPowensProvider(
                    ProviderCredentials.from_env(),
                    date_from=args.date_from,
                    date_to=args.date_to,
                ),
                account_configs=load_account_configs(args.config),
            )
        snapshot = connector.collect()
        write_snapshot(snapshot, args.output)
        print(f"snapshot written: {args.output}")
        return 0

    if args.command == "validate":
        snapshot = read_snapshot(args.snapshot)
        print(f"valid snapshot: {snapshot.run_id} ({len(snapshot.accounts)} accounts)")
        return 0

    if args.command == "discover-accounts":
        provider = RealPowensProvider(ProviderCredentials.from_env())
        payload = provider.list_accounts_payload()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"accounts written: {args.output}")
        return 0

    if args.command == "init-user":
        payload = RealPowensProvider.init_user_token(ProviderCredentials.from_env())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"user token response written: {args.output}")
        return 0

    if args.command == "create-webview-url":
        provider = RealPowensProvider(ProviderCredentials.from_env())
        code_payload = provider.generate_temporary_code()
        code = code_payload.get("code")
        if not isinstance(code, str) or not code:
            parser.error("Powens temporary code response did not contain code")
        url = provider.connect_webview_url(
            redirect_uri=args.redirect_uri,
            code=code,
            state=args.state,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{url}\n", encoding="utf-8")
        print(f"webview URL written: {args.output}")
        return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
