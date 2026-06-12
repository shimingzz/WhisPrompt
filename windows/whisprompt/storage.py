"""Persistent prompt history (data/history.json) with archive/delete."""
import json
import logging
import threading
import uuid

from .config import DATA_DIR

log = logging.getLogger(__name__)
HISTORY_FILE = DATA_DIR / "history.json"


class HistoryStore:
    """Thread-safe append/delete/archive over a single JSON file."""

    def __init__(self):
        self._lock = threading.Lock()
        self._items: list[dict] = []
        if HISTORY_FILE.exists():
            try:
                self._items = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                log.warning("history.json corrupt; starting empty")

    def _save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(
            json.dumps(self._items, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    def add(self, data: dict) -> dict:
        entry = {"id": uuid.uuid4().hex[:12], "archived": False, **data}
        with self._lock:
            self._items.append(entry)
            self._save()
        return entry

    def list(self, archived: bool | None = None) -> list[dict]:
        with self._lock:
            items = list(self._items)
        if archived is None:
            return items
        return [i for i in items if i.get("archived", False) == archived]

    def get(self, item_id: str) -> dict | None:
        with self._lock:
            return next((i for i in self._items if i["id"] == item_id), None)

    def delete(self, item_id: str) -> bool:
        with self._lock:
            before = len(self._items)
            self._items = [i for i in self._items if i["id"] != item_id]
            if len(self._items) != before:
                self._save()
                return True
        return False

    def update(self, item_id: str, **fields) -> dict | None:
        with self._lock:
            for item in self._items:
                if item["id"] == item_id:
                    item.update(fields)
                    self._save()
                    return item
        return None

    def set_archived(self, item_id: str, archived: bool) -> dict | None:
        with self._lock:
            for item in self._items:
                if item["id"] == item_id:
                    item["archived"] = archived
                    self._save()
                    return item
        return None
