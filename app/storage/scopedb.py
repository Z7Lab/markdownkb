"""SQLite persistence for named document scopes (source collections)."""

import json
import logging
import sqlite3
import threading
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS scopes (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    folders    TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class ScopeDB:
    """Persists named scopes in SQLite."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "scopes.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_CREATE_SQL)
        self._lock = threading.Lock()
        self._conn.commit()
        logger.info("ScopeDB opened: %s", db_path)

    def create(self, name: str, folders: list[str]) -> str:
        """Create a scope and return its ID."""
        scope_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._conn.execute(
                "INSERT INTO scopes (id, name, folders) VALUES (?, ?, ?)",
                (scope_id, name, json.dumps(folders)),
            )
            self._conn.commit()
        return scope_id

    def list_scopes(self) -> list[dict]:
        """Return all scopes, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, name, folders, created_at FROM scopes ORDER BY created_at DESC",
            ).fetchall()
        return [
            {**dict(r), "folders": json.loads(r["folders"])}
            for r in rows
        ]

    def get(self, scope_id: str) -> dict | None:
        """Return a single scope by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT id, name, folders, created_at FROM scopes WHERE id = ?",
                (scope_id,),
            ).fetchone()
        if not row:
            return None
        return {**dict(row), "folders": json.loads(row["folders"])}

    def update(self, scope_id: str, name: str, folders: list[str]) -> bool:
        """Update a scope. Returns True if it existed."""
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE scopes SET name = ?, folders = ? WHERE id = ?",
                (name, json.dumps(folders), scope_id),
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
        self._conn.close()
