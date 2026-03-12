"""Storage layer — SQLite-based persistence."""

import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseSQLiteDB:
    """Common SQLite connection setup used by all DB classes.

    Subclasses should pass ``db_name`` (e.g. ``"chats.db"``) and
    ``create_sql`` (the DDL for tables and indices).
    """

    def __init__(self, data_dir: str, db_name: str, create_sql: str):
        db_path = Path(data_dir) / db_name
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(create_sql)
        self._lock = threading.Lock()

    def close(self):
        """Close the database connection."""
        with self._lock:
            self._conn.close()
