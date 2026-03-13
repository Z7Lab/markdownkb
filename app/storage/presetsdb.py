"""SQLite persistence for retrieval setting presets."""

import json
import logging
import sqlite3
import threading
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS presets (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    settings   TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Default retrieval values — kept in sync with RetrievalMixin defaults.
_DEFAULTS = {
    "top_k": 5,
    "score_threshold": 0.3,
    "hybrid_search": True,
    "bm25_weight": 0.5,
}

_VALID_KEYS = frozenset(_DEFAULTS.keys())


class PresetsDB:
    """Persists named retrieval presets in SQLite."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "presets.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_CREATE_SQL)
        self._lock = threading.Lock()
        self._conn.commit()
        logger.info("PresetsDB opened: %s", db_path)

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        d["settings"] = json.loads(d["settings"])
        return d

    def create(self, name: str, settings: dict) -> str:
        """Create a preset and return its ID.

        Raises ValueError if name already exists or settings are invalid.
        """
        self._validate(settings)
        preset_id = uuid.uuid4().hex[:12]
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO presets (id, name, settings) VALUES (?, ?, ?)",
                    (preset_id, name.strip(), json.dumps(settings)),
                )
                self._conn.commit()
            except sqlite3.IntegrityError as e:
                raise ValueError(f"Preset name '{name}' already exists") from e
        return preset_id

    def list_presets(self) -> list[dict]:
        """Return all presets, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM presets ORDER BY created_at DESC",
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get(self, preset_id: str) -> dict | None:
        """Return a single preset by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM presets WHERE id = ?", (preset_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def update(self, preset_id: str, name: str | None = None,
               settings: dict | None = None) -> bool:
        """Update a preset. Returns True if it existed."""
        if settings is not None:
            self._validate(settings)
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM presets WHERE id = ?", (preset_id,),
            ).fetchone()
            if not existing:
                return False
            new_name = name.strip() if name else existing["name"]
            new_settings = json.dumps(settings) if settings else existing["settings"]
            try:
                self._conn.execute(
                    "UPDATE presets SET name = ?, settings = ?, updated_at = datetime('now') WHERE id = ?",
                    (new_name, new_settings, preset_id),
                )
                self._conn.commit()
            except sqlite3.IntegrityError as e:
                raise ValueError(f"Preset name '{new_name}' already exists") from e
        return True

    def delete(self, preset_id: str) -> bool:
        """Delete a preset. Returns True if it existed."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM presets WHERE id = ?", (preset_id,),
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def close(self):
        self._conn.close()

    @staticmethod
    def _validate(settings: dict):
        """Validate preset settings keys and value types."""
        unknown = set(settings.keys()) - _VALID_KEYS
        if unknown:
            raise ValueError(f"Unknown settings keys: {unknown}")
        if "top_k" in settings:
            v = settings["top_k"]
            if not isinstance(v, int) or v < 1 or v > 50:
                raise ValueError("top_k must be an integer between 1 and 50")
        if "score_threshold" in settings:
            v = settings["score_threshold"]
            if not isinstance(v, (int, float)) or v < 0 or v > 1:
                raise ValueError("score_threshold must be between 0.0 and 1.0")
        if "bm25_weight" in settings:
            v = settings["bm25_weight"]
            if not isinstance(v, (int, float)) or v < 0 or v > 1:
                raise ValueError("bm25_weight must be between 0.0 and 1.0")
        if "hybrid_search" in settings and not isinstance(settings["hybrid_search"], bool):
            raise ValueError("hybrid_search must be a boolean")
