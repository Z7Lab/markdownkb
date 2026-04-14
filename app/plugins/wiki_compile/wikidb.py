"""SQLite persistence for managed wiki metadata — owned by the wiki_compile plugin.

Mirrors the BucketDB shape: one table, name-unique, plugin-owned db file
under the configured data directory. A wiki is a name + path pair the
user can address instead of the raw filesystem path.

The directory on disk is *not* managed here — creation, ingest, and
cleanup happen in the service layer. This module only tracks the
registration so the ingest endpoint can resolve a name to a path and
the UI can list known wikis.
"""

import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS wikis (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    path            TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_ingest_at  TEXT,
    page_count      INTEGER NOT NULL DEFAULT 0
);
"""


class WikiDB:
    """Persists managed-wiki metadata in a plugin-owned SQLite database."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "wikis.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()
        self._lock = threading.Lock()
        logger.info("WikiDB opened: %s", db_path)

    def create(self, name: str, path: str) -> dict:
        """Register a new wiki. Raises ValueError on name collision."""
        wiki_id = uuid.uuid4().hex[:12]
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO wikis (id, name, path) VALUES (?, ?, ?)",
                    (wiki_id, name, path),
                )
                self._conn.commit()
            except sqlite3.IntegrityError as e:
                raise ValueError(f"Wiki name already exists: {name}") from e
            row = self._conn.execute(
                "SELECT * FROM wikis WHERE id = ?", (wiki_id,)
            ).fetchone()
        return dict(row)

    def list_all(self) -> list[dict]:
        """Return all wikis, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM wikis ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_by_name(self, name: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM wikis WHERE name = ?", (name,)
            ).fetchone()
        return dict(row) if row else None

    def delete(self, name: str) -> bool:
        """Deregister a wiki. Returns True if a row was removed.
        The directory on disk is *not* touched."""
        with self._lock:
            cursor = self._conn.execute("DELETE FROM wikis WHERE name = ?", (name,))
            self._conn.commit()
        return cursor.rowcount > 0

    def touch_ingest(self, name: str, page_count: int) -> None:
        """Record that an ingest just landed in this wiki."""
        ts = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                "UPDATE wikis SET last_ingest_at = ?, page_count = ? WHERE name = ?",
                (ts, page_count, name),
            )
            self._conn.commit()

    def name_exists(self, name: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM wikis WHERE name = ?", (name,)
            ).fetchone()
        return row is not None

    def close(self) -> None:
        with self._lock:
            self._conn.close()
