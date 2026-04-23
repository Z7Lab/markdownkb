"""SQLite persistence for named document scopes (source collections)."""

import json
import logging
import sqlite3
import threading
import uuid
from pathlib import Path

from app.storage.migrations import run_migrations

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS scopes (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    folders          TEXT NOT NULL DEFAULT '[]',
    tags             TEXT NOT NULL DEFAULT '[]',
    exclude_patterns TEXT NOT NULL DEFAULT '[]',
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "add tags column to scopes",
     "ALTER TABLE scopes ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'"),
    (2, "add exclude_patterns column to scopes",
     "ALTER TABLE scopes ADD COLUMN exclude_patterns TEXT NOT NULL DEFAULT '[]'"),
]


class ScopeDB:
    """Persists named scopes in SQLite."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "scopes.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_CREATE_SQL)
        self._lock = threading.Lock()
        run_migrations(self._conn, _MIGRATIONS, db_label="ScopeDB")
        self._conn.commit()
        logger.info("ScopeDB opened: %s", db_path)

    def create(
        self, name: str, folders: list[str],
        tags: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> str:
        """Create a scope and return its ID."""
        scope_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._conn.execute(
                "INSERT INTO scopes (id, name, folders, tags, exclude_patterns) VALUES (?, ?, ?, ?, ?)",
                (scope_id, name, json.dumps(folders), json.dumps(tags or []), json.dumps(exclude_patterns or [])),
            )
            self._conn.commit()
        return scope_id

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        d["folders"] = json.loads(d["folders"])
        d["tags"] = json.loads(d["tags"])
        d["exclude_patterns"] = json.loads(d["exclude_patterns"])
        return d

    def list_scopes(self) -> list[dict]:
        """Return all scopes, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, name, folders, tags, exclude_patterns, created_at FROM scopes ORDER BY created_at DESC",
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get(self, scope_id: str) -> dict | None:
        """Return a single scope by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT id, name, folders, tags, exclude_patterns, created_at FROM scopes WHERE id = ?",
                (scope_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def update(
        self, scope_id: str, name: str, folders: list[str],
        tags: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> bool:
        """Update a scope. Returns True if it existed."""
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE scopes SET name = ?, folders = ?, tags = ?, exclude_patterns = ? WHERE id = ?",
                (name, json.dumps(folders), json.dumps(tags or []), json.dumps(exclude_patterns or []), scope_id),
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def delete(self, scope_id: str) -> bool:
        """Delete a scope. Returns True if it existed."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM scopes WHERE id = ?", (scope_id,),
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def close(self):
        with self._lock:
            self._conn.close()
