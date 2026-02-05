"""SQLite persistence for chat threads and messages."""

import logging
import sqlite3
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS threads (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id  TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);
"""


class ChatDB:
    """Persists chat threads and messages in SQLite."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "chats.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()
        logger.info("ChatDB opened: %s", db_path)

    def close(self):
        self._conn.close()

    # --- Threads ---

    def create_thread(self, title: str = "") -> str:
        thread_id = uuid.uuid4().hex[:12]
        self._conn.execute(
            "INSERT INTO threads (id, title) VALUES (?, ?)",
            (thread_id, title),
        )
        self._conn.commit()
        return thread_id

    def list_threads(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM threads ORDER BY updated_at DESC",
        ).fetchall()
        return [dict(r) for r in rows]

    def get_thread(self, thread_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM threads WHERE id = ?", (thread_id,),
        ).fetchone()
        return dict(row) if row else None

    def rename_thread(self, thread_id: str, title: str):
        self._conn.execute(
            "UPDATE threads SET title = ?, updated_at = datetime('now') WHERE id = ?",
            (title, thread_id),
        )
        self._conn.commit()

    def delete_thread(self, thread_id: str):
        self._conn.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
        self._conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
        self._conn.commit()

    # --- Messages ---

    def get_messages(self, thread_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE thread_id = ? ORDER BY id ASC",
            (thread_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def add_message(self, thread_id: str, role: str, content: str):
        self._conn.execute(
            "INSERT INTO messages (thread_id, role, content) VALUES (?, ?, ?)",
            (thread_id, role, content),
        )
        self._conn.execute(
            "UPDATE threads SET updated_at = datetime('now') WHERE id = ?",
            (thread_id,),
        )
        self._conn.commit()
