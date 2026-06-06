"""SQLite persistence for bucket metadata — owned by the buckets plugin."""

import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.storage.migrations import run_migrations

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS buckets (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    sources     TEXT NOT NULL DEFAULT '[]',
    file_count  INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT,
    expired     INTEGER NOT NULL DEFAULT 0,
    hidden      INTEGER NOT NULL DEFAULT 0,
    color       TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS file_memberships (
    file_path   TEXT NOT NULL,
    bucket_id   TEXT NOT NULL,
    PRIMARY KEY (file_path, bucket_id)
);

CREATE TABLE IF NOT EXISTS pending_documents (
    id            TEXT PRIMARY KEY,
    bucket_id     TEXT NOT NULL,
    virtual_path  TEXT NOT NULL,
    content       TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_pending_documents_bucket ON pending_documents(bucket_id);
"""

_MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "add expired column to buckets",
     "ALTER TABLE buckets ADD COLUMN expired INTEGER NOT NULL DEFAULT 0"),
    (2, "add color column to buckets",
     "ALTER TABLE buckets ADD COLUMN color TEXT"),
    (3, "create file_memberships table", """
        CREATE TABLE IF NOT EXISTS file_memberships (
            file_path TEXT NOT NULL,
            bucket_id TEXT NOT NULL,
            PRIMARY KEY (file_path, bucket_id)
        )
     """),
    (4, "add description column to buckets",
     "ALTER TABLE buckets ADD COLUMN description TEXT"),
    (5, "add scope_paths column to buckets",
     "ALTER TABLE buckets ADD COLUMN scope_paths TEXT"),
    (6, "create pending_documents table", """
        CREATE TABLE IF NOT EXISTS pending_documents (
            id           TEXT PRIMARY KEY,
            bucket_id    TEXT NOT NULL,
            virtual_path TEXT NOT NULL,
            content      TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        )
     """),
    (7, "index pending_documents by bucket",
     "CREATE INDEX IF NOT EXISTS idx_pending_documents_bucket ON pending_documents(bucket_id)"),
    (8, "add hidden column to buckets",
     "ALTER TABLE buckets ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0"),
]


class BucketDB:
    """Persists bucket metadata in a plugin-owned SQLite database."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "buckets.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_CREATE_SQL)
        run_migrations(self._conn, _MIGRATIONS, db_label="BucketDB")
        self._lock = threading.Lock()
        self._conn.commit()
        logger.info("BucketDB opened: %s", db_path)

    # -- Write operations ----------------------------------------------------

    def create(
        self,
        name: str,
        sources: str,
        file_count: int,
        chunk_count: int,
        expires_at: str | None = None,
        color: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Create a new bucket record. Returns the created row as a dict."""
        bucket_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._conn.execute(
                """INSERT INTO buckets (id, name, sources, file_count, chunk_count, expires_at, color, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (bucket_id, name, sources, file_count, chunk_count, expires_at, color, description),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM buckets WHERE id = ?", (bucket_id,)
            ).fetchone()
        return dict(row)

    def update_counts(self, bucket_id: str, file_count: int, chunk_count: int) -> bool:
        """Update file and chunk counts after adding documents."""
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE buckets SET file_count = ?, chunk_count = ? WHERE id = ?",
                (file_count, chunk_count, bucket_id),
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def update_expiration(self, bucket_id: str, expires_at: str | None) -> bool:
        """Update bucket expiration. Pass None to make permanent."""
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE buckets SET expires_at = ?, expired = 0 WHERE id = ?",
                (expires_at, bucket_id),
            )
            self._conn.commit()
        return cursor.rowcount > 0

    _UPDATABLE_COLUMNS = frozenset({
        "name", "sources", "file_count", "chunk_count",
        "expires_at", "expired", "hidden", "color", "description", "scope_paths",
    })

    def update(self, bucket_id: str, **fields) -> bool:
        """Update allowed columns on a bucket.

        Only keys in :attr:`_UPDATABLE_COLUMNS` are accepted; an unknown key
        raises ``ValueError`` so SQL cannot be composed from user-controlled
        names. ``id`` and ``created_at`` are intentionally immutable.
        """
        if not fields:
            return False
        bad = set(fields) - self._UPDATABLE_COLUMNS
        if bad:
            raise ValueError(f"Unknown bucket columns: {sorted(bad)}")
        cols = list(fields)
        set_clause = ", ".join(f"{c} = ?" for c in cols)
        values = [fields[c] for c in cols] + [bucket_id]
        with self._lock:
            cursor = self._conn.execute(
                f"UPDATE buckets SET {set_clause} WHERE id = ?", values
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def mark_expired(self, bucket_id: str) -> bool:
        """Flag a bucket as expired without deleting it."""
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE buckets SET expired = 1 WHERE id = ?", (bucket_id,)
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def delete(self, bucket_id: str) -> bool:
        """Delete a bucket by ID, including its file memberships and pending documents."""
        with self._lock:
            try:
                self._conn.execute(
                    "DELETE FROM file_memberships WHERE bucket_id = ?", (bucket_id,)
                )
                self._conn.execute(
                    "DELETE FROM pending_documents WHERE bucket_id = ?", (bucket_id,)
                )
                cursor = self._conn.execute(
                    "DELETE FROM buckets WHERE id = ?", (bucket_id,)
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return cursor.rowcount > 0

    # -- File membership operations ------------------------------------------

    def set_file_memberships(self, bucket_id: str, file_paths: list[str]) -> None:
        """Insert file→bucket membership records (INSERT OR IGNORE for idempotency)."""
        if not file_paths:
            return
        with self._lock:
            self._conn.executemany(
                "INSERT OR IGNORE INTO file_memberships (file_path, bucket_id) VALUES (?, ?)",
                [(p, bucket_id) for p in file_paths],
            )
            self._conn.commit()

    # -- Pending documents (async embed queue) --------------------------------

    def add_pending_documents(self, bucket_id: str, docs: list[dict]) -> list[str]:
        """Insert pending virtual documents awaiting embedding. Returns their IDs."""
        ids = [uuid.uuid4().hex[:16] for _ in docs]
        with self._lock:
            self._conn.executemany(
                """INSERT OR IGNORE INTO pending_documents
                   (id, bucket_id, virtual_path, content, content_hash)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (ids[i], bucket_id, doc["virtual_path"], doc["content"], doc["content_hash"])
                    for i, doc in enumerate(docs)
                ],
            )
            self._conn.commit()
        return ids

    def get_pending_documents(self, bucket_id: str) -> list[dict]:
        """Return all pending documents for a bucket."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM pending_documents WHERE bucket_id = ? ORDER BY created_at",
                (bucket_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def remove_pending_documents(self, ids: list[str]) -> None:
        """Delete pending document records by their IDs (called after successful embed)."""
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        with self._lock:
            self._conn.execute(
                f"DELETE FROM pending_documents WHERE id IN ({placeholders})", ids
            )
            self._conn.commit()

    def remove_all_pending_documents(self, bucket_id: str) -> None:
        """Remove all pending documents for a bucket (e.g. on delete)."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM pending_documents WHERE bucket_id = ?", (bucket_id,)
            )
            self._conn.commit()

    def remove_file_memberships(self, bucket_id: str) -> None:
        """Remove all file memberships for a bucket."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM file_memberships WHERE bucket_id = ?", (bucket_id,)
            )
            self._conn.commit()

    def get_bucketed_paths(self) -> set[str]:
        """Return all file paths that belong to at least one bucket."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT file_path FROM file_memberships"
            ).fetchall()
        return {row[0] for row in rows}

    def get_bucketed_path_map(self) -> dict[str, list[str]]:
        """Return a map of file_path → [bucket_ids] for all memberships."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT file_path, bucket_id FROM file_memberships"
            ).fetchall()
        result: dict[str, list[str]] = {}
        for path, bid in rows:
            result.setdefault(path, []).append(bid)
        return result

    # -- Read operations -----------------------------------------------------

    def get(self, bucket_id: str) -> dict | None:
        """Get a single bucket by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM buckets WHERE id = ?", (bucket_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_by_name(self, name: str) -> dict | None:
        """Get a single bucket by name."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM buckets WHERE name = ?", (name,)
            ).fetchone()
        return dict(row) if row else None

    def resolve(self, bucket: str) -> dict | None:
        """Look up a bucket by ID first, then by name."""
        return self.get(bucket) or self.get_by_name(bucket)

    def list_all(self) -> list[dict]:
        """Return all buckets ordered by creation time."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM buckets ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_expired(self) -> list[dict]:
        """Return buckets whose expires_at has passed but are not yet flagged."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM buckets WHERE expires_at IS NOT NULL AND expires_at <= ? AND expired = 0",
                (now,),
            ).fetchall()
        return [dict(r) for r in rows]

    def name_exists(self, name: str) -> bool:
        """Check if a bucket name is already taken."""
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM buckets WHERE name = ?", (name,)
            ).fetchone()
        return row is not None

    # -- Lifecycle -----------------------------------------------------------

    def close(self) -> None:
        self._conn.close()
