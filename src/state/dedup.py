"""Deduplication module to avoid pushing the same items repeatedly."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).parent.parent.parent / "data" / "seen.json"


class DedupStore:
    """Manages a set of seen item IDs with timestamps for expiry."""

    def __init__(self, path: str | Path = DEFAULT_PATH, retention_days: int = 30):
        self.path = Path(path)
        self.retention_days = retention_days
        self._data: dict[str, list[dict]] = {"arxiv": [], "github": [], "pwc": []}
        self._load()

    def _load(self):
        """Load seen records from disk."""
        if self.path.exists():
            try:
                with open(self.path, "r") as f:
                    self._data = json.load(f)
                logger.info(f"Loaded dedup store from {self.path}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Error loading dedup store, starting fresh: {e}")
                self._data = {"arxiv": [], "github": [], "pwc": []}
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self):
        """Persist seen records to disk after pruning old entries."""
        self._prune()
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)
        logger.info(f"Saved dedup store to {self.path}")

    def _prune(self):
        """Remove entries older than retention_days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        for source in self._data:
            original_count = len(self._data[source])
            self._data[source] = [
                entry for entry in self._data[source] if entry.get("seen_at", "") > cutoff
            ]
            pruned = original_count - len(self._data[source])
            if pruned > 0:
                logger.info(f"Pruned {pruned} old entries from {source}")

    def is_seen(self, unique_id: str) -> bool:
        """Check if an item has been seen before.

        Args:
            unique_id: The unique identifier (e.g. "arxiv:2401.12345").

        Returns:
            True if already seen.
        """
        source = unique_id.split(":")[0]
        entries = self._data.get(source, [])
        return any(e.get("id") == unique_id for e in entries)

    def mark_seen(self, unique_id: str):
        """Mark an item as seen.

        Args:
            unique_id: The unique identifier.
        """
        source = unique_id.split(":")[0]
        if source not in self._data:
            self._data[source] = []

        if not self.is_seen(unique_id):
            self._data[source].append(
                {"id": unique_id, "seen_at": datetime.now(timezone.utc).isoformat()}
            )

    def filter_unseen(self, items: list) -> list:
        """Filter a list of items to only include unseen ones.

        Items must have a 'unique_id' property.

        Args:
            items: List of items with unique_id property.

        Returns:
            List of items that haven't been seen before.
        """
        unseen = []
        for item in items:
            uid = item.unique_id
            if not self.is_seen(uid):
                unseen.append(item)
                self.mark_seen(uid)

        logger.info(f"Dedup: {len(items)} items -> {len(unseen)} unseen")
        return unseen
