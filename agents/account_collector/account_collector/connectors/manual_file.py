from __future__ import annotations

from pathlib import Path

from account_collector.connectors.base import AccountConnector
from account_collector.models import CollectionSnapshot
from account_collector.normalizer import normalize_snapshot
from account_collector.snapshot_writer import read_snapshot


class ManualFileConnector(AccountConnector):
    name = "manual_file"

    def __init__(self, input_path: Path):
        self.input_path = input_path

    def collect(self) -> CollectionSnapshot:
        return normalize_snapshot(read_snapshot(self.input_path))
