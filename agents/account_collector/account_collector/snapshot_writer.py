from __future__ import annotations

import json
from pathlib import Path

from .models import CollectionSnapshot


def write_snapshot(snapshot: CollectionSnapshot, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_snapshot(input_path: Path) -> CollectionSnapshot:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("snapshot file must contain a JSON object")
    return CollectionSnapshot.from_dict(payload)
