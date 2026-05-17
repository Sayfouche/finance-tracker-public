from __future__ import annotations

from datetime import UTC, datetime

from .models import CollectionSnapshot


def normalize_snapshot(snapshot: CollectionSnapshot) -> CollectionSnapshot:
    accounts = sorted(snapshot.accounts, key=lambda item: item.external_id)
    errors = sorted(set(snapshot.errors))
    snapshot_date = snapshot.snapshot_date
    if snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=UTC)

    return CollectionSnapshot(
        snapshot_date=snapshot_date,
        source=snapshot.source,
        run_id=snapshot.run_id,
        accounts=accounts,
        errors=errors,
    )
