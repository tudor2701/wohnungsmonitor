"""Persistente Speicherung bereits gesehener Inserate (JSON-Datei)."""

import json
import logging
import os
from datetime import datetime

from config import SEEN_LISTINGS_FILE

logger = logging.getLogger(__name__)


class SeenListings:
    """Verwaltet eine JSON-Datei mit den IDs bereits gemeldeter Inserate."""

    def __init__(self, filepath: str = SEEN_LISTINGS_FILE):
        self.filepath = filepath
        self._data: dict = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.filepath):
            return {}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Konnte {self.filepath} nicht laden: {e}. Starte mit leerem Datensatz.")
            return {}

    def _save(self) -> None:
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"Konnte {self.filepath} nicht speichern: {e}")

    def is_new(self, key: str) -> bool:
        """Gibt True zurück, wenn das Inserat noch nicht gesehen wurde."""
        return key not in self._data

    def mark_as_seen(self, key: str) -> None:
        """Markiert ein Inserat als gesehen und speichert es persistent."""
        self._data[key] = datetime.now().isoformat()
        self._save()

    def count(self) -> int:
        return len(self._data)
