"""SQLite-backed persistence for Settings._data.

Settings are stored as a single JSON blob so the existing mixin-based
Settings API (read from / write to ``self._data``) requires no changes.
All mutations still happen in-memory; ``save()`` flushes the blob to the
database instead of writing YAML.

The database always lives at ``<data_dir>/markdownkb_settings.db``.
``data_dir`` is resolved via the ``MARKDOWNKB_DATA_DIR`` env var (or
``platformdirs.user_data_dir("markdownkb")`` as a fallback) — the same
logic used for every other database in the stack.  This is intentionally
independent of any ``storage.data_directory`` override that might live
*inside* settings themselves, to avoid a circular bootstrap dependency.
"""

import json
import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

_DATA_KEY = "data"


class SettingsDB:
    """Thin SQLite wrapper that persists the Settings ``_data`` dictionary.

    Thread-safe: a single connection is shared and protected by a lock.
    WAL mode is enabled so concurrent reads don't block the write.
    """

    DB_FILENAME = "markdownkb_settings.db"

    def __init__(self, data_dir: str | Path) -> None:
        db_path = Path(data_dir) / self.DB_FILENAME
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_SCHEMA)
        self._conn.commit()
        logger.debug("SettingsDB opened at %s", db_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def path(self) -> Path:
        """Absolute path to the database file."""
        return self._path

    def load(self) -> dict | None:
        """Return the stored settings dict, or ``None`` if nothing has been saved yet.

        Returns ``None`` (not an empty dict) so callers can distinguish
        "never persisted" from "persisted as empty."
        """
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (_DATA_KEY,)
        ).fetchone()
        if row is None:
            return None
        try:
            result = json.loads(row[0])
            if not isinstance(result, dict):
                logger.error(
                    "SettingsDB: stored value is not a dict (%s) — treating as empty",
                    type(result).__name__,
                )
                return None
            return result
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error("SettingsDB: invalid JSON in settings row: %s — treating as empty", exc)
            return None

    def save(self, data: dict) -> None:
        """Atomically replace the stored settings dict."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (_DATA_KEY, json.dumps(data)),
            )
            self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self._conn.close()
