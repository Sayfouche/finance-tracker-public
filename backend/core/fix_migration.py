"""
Placeholder for private one-shot migration scripts.

Project-specific spreadsheet cleanup code should live outside the public
repository, for example in ``backend/private/`` or another ignored path.
"""


def run_private_migration() -> None:
    raise RuntimeError(
        "No public migration is bundled. Keep personal migration scripts outside Git."
    )


if __name__ == "__main__":
    run_private_migration()
