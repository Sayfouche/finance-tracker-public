import argparse
from pathlib import Path

from core.powens_cleanup import cleanup_powens_imports
from db.database import SessionLocal


DEFAULT_BACKUP_DIR = Path(__file__).resolve().parents[2] / "agents" / "account_collector" / "backups"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = cleanup_powens_imports(db, backup_dir=args.backup_dir, apply=args.apply)
        print({
            "backup_path": str(result.backup_path),
            "transactions": result.transactions,
            "external_transactions": result.external_transactions,
            "patrimony_snapshots": result.patrimony_snapshots,
            "agent_runs": result.agent_runs,
            "agent_run_errors": result.agent_run_errors,
            "applied": result.applied,
        })
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
