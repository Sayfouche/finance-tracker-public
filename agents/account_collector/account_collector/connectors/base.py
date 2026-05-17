from __future__ import annotations

from abc import ABC, abstractmethod

from account_collector.models import CollectionSnapshot


class AccountConnector(ABC):
    name: str

    @abstractmethod
    def collect(self) -> CollectionSnapshot:
        """Collect accounts and return a normalized snapshot."""
