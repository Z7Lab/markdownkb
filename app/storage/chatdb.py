"""SQLite persistence for chat threads and messages."""

import json
import logging
import sqlite3
import threading
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
    sources    TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);
"""

# Ordered list of migrations. Each entry is (version, description, sql).
# version numbers must be sequential starting from 1.
# New tables created by _CREATE_SQL should include the column from the start;
# the migration here is only for upgrading existing databases.
_MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "add sources column to messages", "ALTER TABLE messages ADD COLUMN sources TEXT"),
]


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
        self._lock = threading.Lock()
        self._run_migrations()
        self._conn.commit()
        logger.info("ChatDB opened: %s", db_path)

    def _run_migrations(self):
        """Apply any pending schema migrations using PRAGMA user_version."""
        current = self._conn.execute("PRAGMA user_version").fetchone()[0]
        target = len(_MIGRATIONS)
        if current >= target:
            return
        for version, description, sql in _MIGRATIONS:
            if version <= current:
                continue
            try:
                self._conn.execute(sql)
                logger.info("Migration %d applied: %s", version, description)
            except sqlite3.OperationalError:
                # Column/table already exists (fresh DB created with latest schema)
                logger.debug("Migration %d skipped (already applied): %s", version, description)
        # PRAGMA statements don't support parameterized queries in SQLite;
        # target is derived from len(_MIGRATIONS) (code-controlled int), not user input.
        self._conn.execute(f"PRAGMA user_version = {int(target)}")
        self._conn.commit()

    def close(self):
        """Close the database connection."""
        with self._lock:
            self._conn.close()

    # --- Threads ---

    def create_thread(self, title: str = "") -> str:
        """Create a new chat thread and return its ID."""
        thread_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._conn.execute(
                "INSERT INTO threads (id, title) VALUES (?, ?)",
                (thread_id, title),
            )
            self._conn.commit()
        return thread_id

    def list_threads(
        self, *, offset: int = 0, limit: int | None = None,
    ) -> list[dict]:
        """List chat threads ordered by most recently updated, with optional pagination."""
        with self._lock:
            sql = "SELECT * FROM threads ORDER BY updated_at DESC"
            params: list = []
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                params = [limit, offset]
            rows = self._conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def thread_count(self) -> int:
        """Return total number of threads."""
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) as cnt FROM threads").fetchone()
            return row["cnt"]

    def get_thread(self, thread_id: str) -> dict | None:
        """Get a specific thread by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM threads WHERE id = ?",
                (thread_id,),
            ).fetchone()
            return dict(row) if row else None

    def rename_thread(self, thread_id: str, title: str):
        """Rename a thread and update its timestamp."""
        with self._lock:
            self._conn.execute(
                "UPDATE threads SET title = ?, updated_at = datetime('now') WHERE id = ?",
                (title, thread_id),
            )
            self._conn.commit()

    def delete_thread(self, thread_id: str):
        """Delete a thread and all its messages."""
        with self._lock:
            self._conn.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
            self._conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            self._conn.commit()

    # --- Messages ---

    def get_messages(self, thread_id: str) -> list[dict]:
        """Get all messages for a thread in chronological order."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE thread_id = ? ORDER BY id ASC",
                (thread_id,),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                raw = d.get("sources")
                d["sources"] = json.loads(raw) if raw else None
                out.append(d)
            return out

    def add_message(
        self, thread_id: str, role: str, content: str, sources: list[str] | None = None
    ):
        """Add a new message to a thread and update the thread's timestamp."""
        src_json = json.dumps(sources) if sources else None
        with self._lock:
            self._conn.execute(
                "INSERT INTO messages (thread_id, role, content, sources) VALUES (?, ?, ?, ?)",
                (thread_id, role, content, src_json),
            )
            self._conn.execute(
                "UPDATE threads SET updated_at = datetime('now') WHERE id = ?",
                (thread_id,),
            )
            self._conn.commit()

    def set_sources(self, thread_id: str, message_role: str, sources: list[str]):
        """Update sources on the most recent message of the given role in a thread."""
        with self._lock:
            self._conn.execute(
                """UPDATE messages SET sources = ?
                   WHERE id = (
                       SELECT id FROM messages
                       WHERE thread_id = ? AND role = ?
                       ORDER BY id DESC LIMIT 1
                   )""",
                (json.dumps(sources), thread_id, message_role),
            )
            self._conn.commit()

    def clear_all(self):
        """Delete all threads and messages."""
        with self._lock:
            self._conn.execute("DELETE FROM messages")
            self._conn.execute("DELETE FROM threads")
            self._conn.commit()
            # Reclaim disk space and truncate WAL
            self._conn.execute("VACUUM")
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def vacuum(self):
        """Reclaim disk space by rebuilding the database file."""
        with self._lock:
            self._conn.execute("VACUUM")
            # Checkpoint WAL to truncate .db-wal file
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
