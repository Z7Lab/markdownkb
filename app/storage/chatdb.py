"""SQLite persistence for chat threads and messages."""

import json
import logging
import sqlite3
import threading
import uuid
from pathlib import Path

from app.storage.migrations import run_migrations

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS threads (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    bucket_id  TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id   TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    sources     TEXT,
    source_map  TEXT,
    provider    TEXT,
    model       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);
"""

# Ordered list of migrations. Each entry is (version, description, sql).
# version numbers must be sequential starting from 1.
# New tables created by _CREATE_SQL should include the column from the start;
# the migration here is only for upgrading existing databases.
_MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "add sources column to messages", "ALTER TABLE messages ADD COLUMN sources TEXT"),
    (2, "add source_map column to messages", "ALTER TABLE messages ADD COLUMN source_map TEXT"),
    (3, "add provider column to messages", "ALTER TABLE messages ADD COLUMN provider TEXT"),
    (4, "add model column to messages", "ALTER TABLE messages ADD COLUMN model TEXT"),
    (5, "add bucket_id column to threads (bucket-owned chats)",
     "ALTER TABLE threads ADD COLUMN bucket_id TEXT"),
]


class ChatDB:
    """Persists chat threads and messages in SQLite."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "chats.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_CREATE_SQL)
        self._lock = threading.Lock()
        self._run_migrations()
        self._conn.commit()
        logger.info("ChatDB opened: %s", db_path)

    def _run_migrations(self):
        run_migrations(self._conn, _MIGRATIONS, db_label="ChatDB")

    def close(self):
        """Close the database connection."""
        with self._lock:
            self._conn.close()

    # --- Threads ---

    def create_thread(self, title: str = "", bucket_id: str | None = None) -> str:
        """Create a new chat thread and return its ID.

        ``bucket_id`` marks the thread as owned by a bucket (bucket-local chat);
        ``None`` is a normal global thread shown in the Chat tab.
        """
        thread_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._conn.execute(
                "INSERT INTO threads (id, title, bucket_id) VALUES (?, ?, ?)",
                (thread_id, title, bucket_id),
            )
            self._conn.commit()
        return thread_id

    def _ownership_clause(self, only_global: bool, bucket_id: str | None) -> tuple[str, list]:
        """Build a WHERE clause for thread-ownership filtering.

        ``bucket_id`` set → that bucket's threads. ``only_global`` → unowned
        (Chat tab) threads. Neither → all threads.
        """
        if bucket_id is not None:
            return " WHERE bucket_id = ?", [bucket_id]
        if only_global:
            return " WHERE bucket_id IS NULL", []
        return "", []

    def list_threads(
        self, *, offset: int = 0, limit: int | None = None,
        only_global: bool = False, bucket_id: str | None = None,
    ) -> list[dict]:
        """List chat threads ordered by most recently updated, with optional pagination.

        By default returns all threads. Pass ``only_global=True`` for unowned
        (Chat tab) threads, or ``bucket_id`` for a single bucket's threads.
        """
        where, params = self._ownership_clause(only_global, bucket_id)
        with self._lock:
            sql = f"SELECT * FROM threads{where} ORDER BY updated_at DESC"
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                params = params + [limit, offset]
            rows = self._conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def thread_count(self, *, only_global: bool = False, bucket_id: str | None = None) -> int:
        """Return the number of threads, with the same ownership filtering as list_threads."""
        where, params = self._ownership_clause(only_global, bucket_id)
        with self._lock:
            row = self._conn.execute(
                f"SELECT COUNT(*) as cnt FROM threads{where}", params
            ).fetchone()
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
        """Rename a thread without changing its timestamp."""
        with self._lock:
            self._conn.execute(
                "UPDATE threads SET title = ? WHERE id = ?",
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
                if raw:
                    try:
                        d["sources"] = json.loads(raw)
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.error(
                            "ChatDB: corrupt JSON in 'sources' for message id=%s thread=%s — "
                            "substituting None. Error: %s",
                            d.get("id"), thread_id, e,
                        )
                        d["sources"] = None
                        d["_data_corrupt"] = True
                else:
                    d["sources"] = None
                raw_map = d.get("source_map")
                if raw_map:
                    try:
                        d["source_map"] = json.loads(raw_map)
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.error(
                            "ChatDB: corrupt JSON in 'source_map' for message id=%s thread=%s — "
                            "substituting None. Error: %s",
                            d.get("id"), thread_id, e,
                        )
                        d["source_map"] = None
                        d.setdefault("_data_corrupt", True)
                else:
                    d["source_map"] = None
                out.append(d)
            return out

    def add_message(
        self, thread_id: str, role: str, content: str,
        sources: list[str] | None = None,
        provider: str | None = None, model: str | None = None,
    ):
        """Add a new message to a thread and update the thread's timestamp."""
        src_json = json.dumps(sources) if sources else None
        with self._lock:
            self._conn.execute(
                "INSERT INTO messages (thread_id, role, content, sources, provider, model) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (thread_id, role, content, src_json, provider, model),
            )
            self._conn.execute(
                "UPDATE threads SET updated_at = datetime('now') WHERE id = ?",
                (thread_id,),
            )
            self._conn.commit()

    def set_sources(
        self, thread_id: str, message_role: str, sources: list[str],
        source_map: dict[str, str] | None = None,
    ):
        """Update sources (and optional source map) on the most recent message."""
        with self._lock:
            self._conn.execute(
                """UPDATE messages SET sources = ?, source_map = ?
                   WHERE id = (
                       SELECT id FROM messages
                       WHERE thread_id = ? AND role = ?
                       ORDER BY id DESC LIMIT 1
                   )""",
                (json.dumps(sources),
                 json.dumps(source_map) if source_map else None,
                 thread_id, message_role),
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
