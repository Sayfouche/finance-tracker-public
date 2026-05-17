"""
Optional local authentication smoke test for a Woob-compatible provider.

Real provider module names and credentials must be supplied via environment
variables and must not be committed.
"""
import os


def main() -> None:
    module = os.getenv("WOOB_PROVIDER_MODULE")
    login = os.getenv("WOOB_PROVIDER_LOGIN")
    password = os.getenv("WOOB_PROVIDER_PASSWORD")
    if not module or not login or not password:
        raise SystemExit(
            "Set WOOB_PROVIDER_MODULE, WOOB_PROVIDER_LOGIN and WOOB_PROVIDER_PASSWORD."
        )

    from woob.core import Woob

    woob = Woob()
    try:
        woob.load_backend(module, module, params={"login": login, "password": password})
        backend = woob.get_backend(module)
        accounts = list(backend.iter_accounts())
        print(f"Authentication OK. Accounts found: {len(accounts)}")
    finally:
        woob.deinit()


if __name__ == "__main__":
    main()
