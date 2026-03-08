"""SQLite persistence for saved plans."""

import logging
import sqlite3
import threading
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS plans (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,
    query      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class PlanDB:
    """Persists generated plans in SQLite."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "plans.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_CREATE_SQL)
        self._lock = threading.Lock()
        self._conn.commit()
        logger.info("PlanDB opened: %s", db_path)

    def save(self, title: str, content: str, query: str = "") -> str:
        """Save a plan and return its ID."""
        plan_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._conn.execute(
                "INSERT INTO plans (id, title, content, query) VALUES (?, ?, ?, ?)",
                (plan_id, title, content, query),
            )
            self._conn.commit()
        return plan_id

    def list_plans(self) -> list[dict]:
        """Return all plans, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, title, query, created_at FROM plans ORDER BY created_at DESC",
            ).fetchall()
        return [dict(r) for r in rows]

    def get(self, plan_id: str) -> dict | None:
        """Return a single plan by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT id, title, content, query, created_at FROM plans WHERE id = ?",
                (plan_id,),
            ).fetchone()
        return dict(row) if row else None

    def delete(self, plan_id: str) -> bool:
        """Delete a plan. Returns True if it existed."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM plans WHERE id = ?", (plan_id,),
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def close(self):
        self._conn.close()
