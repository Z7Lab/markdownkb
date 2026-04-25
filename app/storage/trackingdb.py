"""SQLite tracking database for the indexing pipeline.

SQLite is the source of truth for *what's indexed*.
ChromaDB remains the source of truth for *the actual vectors*.
"""

import logging
import sqlite3
import threading
from pathlib import Path

from app.storage.migrations import run_migrations

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS indexed_files (
    path        TEXT PRIMARY KEY,
    source_root TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    file_size   INTEGER NOT NULL,
    mtime       REAL NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'pending',
    error_msg   TEXT,
    indexed_at  TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    include_rag INTEGER NOT NULL DEFAULT 1,
    tags        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS file_metadata (
    path        TEXT PRIMARY KEY,
    include_rag INTEGER NOT NULL DEFAULT 1,
    tags        TEXT NOT NULL DEFAULT '',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_files_source_root
    ON indexed_files(source_root);
CREATE INDEX IF NOT EXISTS idx_files_status
    ON indexed_files(status);
"""


def _migrate_v1_to_v2(conn: sqlite3.Connection):
    """Add include_rag column; convert status='excluded' to include_rag=0."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(indexed_files)")]
    if "include_rag" not in cols:
        conn.execute(
            "ALTER TABLE indexed_files "
            "ADD COLUMN include_rag INTEGER NOT NULL DEFAULT 1"
        )
    conn.execute(
        "UPDATE indexed_files SET include_rag = 0, status = 'pending' "
        "WHERE status = 'excluded'"
    )
    conn.commit()
    logger.info("Migrated schema v1 → v2: added include_rag column")


def _migrate_v2_to_v3(conn: sqlite3.Connection):
    """Add tags column for storing file-level tags from frontmatter."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(indexed_files)")]
    if "tags" not in cols:
        conn.execute(
            "ALTER TABLE indexed_files ADD COLUMN tags TEXT NOT NULL DEFAULT ''"
        )
        conn.commit()
        logger.info("Migrated schema v2 → v3: added tags column")


def _migrate_v3_to_v4(conn: sqlite3.Connection):
    """Create file_metadata table and copy tags/include_rag from indexed_files.

    The file_metadata table survives clear() so user preferences (tags,
    RAG inclusion) persist across model switches and reindexes.
    """
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    if "file_metadata" not in tables:
        conn.execute("""
            CREATE TABLE file_metadata (
                path        TEXT PRIMARY KEY,
                include_rag INTEGER NOT NULL DEFAULT 1,
                tags        TEXT NOT NULL DEFAULT '',
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        # Copy existing user metadata from indexed_files
        conn.execute("""
            INSERT INTO file_metadata (path, include_rag, tags, updated_at)
            SELECT path, include_rag, tags, updated_at
            FROM indexed_files
            WHERE tags != '' OR include_rag != 1
        """)
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM file_metadata").fetchone()[0]
        logger.info(
            "Migrated schema v3 → v4: created file_metadata table (%d rows copied)",
            count,
        )


def _migrate_v4_to_v5(conn: sqlite3.Connection):
    """Backfill indexed_at for rows that were indexed before the column existed."""
    count = conn.execute(
        "UPDATE indexed_files SET indexed_at = updated_at "
        "WHERE indexed_at IS NULL AND status = 'complete' AND chunk_count > 0"
    ).rowcount
    conn.commit()
    if count:
        logger.info(
            "Migrated schema v4 → v5: backfilled indexed_at for %d files", count
        )


_MIGRATIONS = [
    (1, "add include_rag column + reset excluded", _migrate_v1_to_v2),
    (2, "add tags column", _migrate_v2_to_v3),
    (3, "create file_metadata table", _migrate_v3_to_v4),
    (4, "backfill indexed_at", _migrate_v4_to_v5),
]


class TrackingDB:
    """Tracks indexed file states in SQLite."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "markdownkb.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(db_path), check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._lock = threading.Lock()
        self._init_schema()
        logger.info("TrackingDB opened: %s", db_path)

    def _init_schema(self):
        """Create tables if they don't exist, then run migrations.

        Also supports a one-time upgrade from the legacy bespoke
        ``schema_version`` table: its version is copied into
        ``PRAGMA user_version`` (after normalizing — the old scheme counted
        schema v1 as "created," the canonical runner counts migrations
        applied, so we subtract one) and the table is dropped.
        """
        self._conn.executescript(_CREATE_SQL)

        legacy = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        if legacy is not None:
            row = self._conn.execute(
                "SELECT version FROM schema_version LIMIT 1"
            ).fetchone()
            legacy_version = row["version"] if row else 1
            applied = max(0, int(legacy_version) - 1)
            self._conn.execute(f"PRAGMA user_version = {applied}")
            self._conn.execute("DROP TABLE schema_version")
            self._conn.commit()

        run_migrations(self._conn, _MIGRATIONS, db_label="TrackingDB")

    def close(self):
        """Close the database connection."""
        with self._lock:
            self._conn.close()

    # --- Single-file queries ---

    def get_file(self, path: str) -> dict | None:
        """Return the tracked state for a single file, or None.

        Merges include_rag from file_metadata table (authoritative for RAG prefs).
        """
        with self._lock:
            row = self._conn.execute(
                """SELECT f.*,
                    COALESCE(m.include_rag, f.include_rag) AS include_rag
                FROM indexed_files f
                LEFT JOIN file_metadata m ON m.path = f.path
                WHERE f.path = ?""",
                (path,),
            ).fetchone()
            return dict(row) if row else None

    def get_hash(self, path: str) -> str | None:
        """Return the stored content_hash for a file, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT content_hash FROM indexed_files WHERE path = ?",
                (path,),
            ).fetchone()
            return row["content_hash"] if row else None

    # --- Bulk queries ---

    def get_all_files(
        self, *, offset: int = 0, limit: int | None = None,
    ) -> list[dict]:
        """Return tracked files ordered by path, with optional pagination.

        Merges include_rag from file_metadata table.
        """
        with self._lock:
            sql = """SELECT f.*,
                COALESCE(m.include_rag, f.include_rag) AS include_rag
            FROM indexed_files f
            LEFT JOIN file_metadata m ON m.path = f.path
            ORDER BY f.path"""
            params: list = []
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                params = [limit, offset]
            rows = self._conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_hash_map(self) -> dict[str, str]:
        """Return {path: content_hash} for successfully indexed files.
        Error-status files are excluded so the indexer always retries them."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT path, content_hash FROM indexed_files WHERE status != 'error'"
            ).fetchall()
            return {r["path"]: r["content_hash"] for r in rows}

    def get_files_by_status(self, status: str) -> list[dict]:
        """Return files with a given status."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM indexed_files WHERE status = ?",
                (status,),
            ).fetchall()
            return [dict(r) for r in rows]

    def recover_incomplete(self) -> list[str]:
        """Return paths stuck in 'indexing' status (crashed mid-index)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT path FROM indexed_files WHERE status = 'indexing'"
            ).fetchall()
            return [r["path"] for r in rows]

    def reset_incomplete(self) -> int:
        """Reset files stuck in 'indexing' to 'pending' (e.g. after a crash).

        Returns the number of files reset.
        """
        with self._lock:
            cursor = self._conn.execute(
                """UPDATE indexed_files
                SET status = 'pending', chunk_count = 0,
                    updated_at = datetime('now')
                WHERE status = 'indexing'"""
            )
            self._conn.commit()
            return cursor.rowcount

    # --- Mutations ---

    def upsert_file(
        self, path: str, source_root: str,
        content_hash: str, file_size: int, mtime: float, *,
        status: str = "pending", chunk_count: int = 0,
    ):
        """Insert or update a file's tracking record.

        On insert after a clear(), restores include_rag from file_metadata
        so user preferences survive model switches.
        """
        with self._lock:
            # Restore include_rag from metadata if this is a re-insert after clear()
            meta = self._conn.execute(
                "SELECT include_rag FROM file_metadata WHERE path = ?",
                (path,),
            ).fetchone()
            include_rag = meta["include_rag"] if meta else 1

            self._conn.execute(
                """INSERT INTO indexed_files
                    (path, source_root, content_hash, file_size, mtime,
                     chunk_count, status, include_rag, updated_at,
                     indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'),
                        CASE WHEN ? = 'complete' THEN datetime('now') ELSE NULL END)
                ON CONFLICT(path) DO UPDATE SET
                    source_root = excluded.source_root,
                    content_hash = excluded.content_hash,
                    file_size = excluded.file_size,
                    mtime = excluded.mtime,
                    chunk_count = excluded.chunk_count,
                    status = excluded.status,
                    error_msg = NULL,
                    indexed_at = CASE
                        WHEN excluded.status = 'complete'
                        THEN datetime('now')
                        ELSE indexed_files.indexed_at
                    END,
                    updated_at = datetime('now')
                """,
                (path, source_root, content_hash, file_size, mtime,
                 chunk_count, status, include_rag, status),
            )
            self._conn.commit()

    def mark_indexing(self, path: str):
        """Set status='indexing' as a crash recovery marker."""
        with self._lock:
            self._conn.execute(
                """UPDATE indexed_files
                SET status = 'indexing', updated_at = datetime('now')
                WHERE path = ?""",
                (path,),
            )
            self._conn.commit()

    def mark_complete(self, path: str, chunk_count: int):
        """Set status='complete' with chunk count and timestamp."""
        with self._lock:
            self._conn.execute(
                """UPDATE indexed_files
                SET status = 'complete', chunk_count = ?,
                    indexed_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE path = ?""",
                (chunk_count, path),
            )
            self._conn.commit()

    def mark_error(self, path: str, error_msg: str):
        """Set status='error' with error message. Clears content_hash so the
        file is retried on the next index scan rather than skipped."""
        with self._lock:
            self._conn.execute(
                """UPDATE indexed_files
                SET status = 'error', error_msg = ?, content_hash = '',
                    updated_at = datetime('now')
                WHERE path = ?""",
                (error_msg, path),
            )
            self._conn.commit()

    def set_include_rag(self, path: str, include: bool):
        """Toggle whether a file is included in RAG search results."""
        val = 1 if include else 0
        with self._lock:
            self._conn.execute(
                """INSERT INTO file_metadata (path, include_rag, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(path) DO UPDATE SET
                    include_rag = excluded.include_rag,
                    updated_at = excluded.updated_at""",
                (path, val),
            )
            # Keep indexed_files in sync
            self._conn.execute(
                "UPDATE indexed_files SET include_rag = ? WHERE path = ?",
                (val, path),
            )
            self._conn.commit()

    def get_rag_excluded_paths(self) -> set[str]:
        """Return paths of files excluded from RAG search.

        Checks file_metadata (authoritative), union with indexed_files
        for rows not yet migrated.
        """
        with self._lock:
            rows = self._conn.execute(
                """SELECT path FROM file_metadata WHERE include_rag = 0
                UNION
                SELECT path FROM indexed_files WHERE include_rag = 0
                    AND path NOT IN (SELECT path FROM file_metadata)"""
            ).fetchall()
            return {r["path"] for r in rows}

    def unindex_file(self, path: str):
        """Reset a file to un-indexed state (keeps tracking record).

        Preserves include_rag preference — unindexing removes chunks
        but doesn't change the user's RAG inclusion setting.
        """
        with self._lock:
            self._conn.execute(
                """UPDATE indexed_files
                SET status = 'pending', chunk_count = 0,
                    content_hash = '',
                    updated_at = datetime('now')
                WHERE path = ?""",
                (path,),
            )
            self._conn.commit()

    def rename_file(self, old_path: str, new_path: str,
                    new_source_root: str) -> bool:
        """Move a tracking record to a new path, preserving all state.

        Also updates file_metadata (include_rag) if present.
        Returns True if the old record was found and moved.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM indexed_files WHERE path = ?", (old_path,),
            ).fetchone()
            if not row:
                return False
            rec = dict(row)
            self._conn.execute(
                "DELETE FROM indexed_files WHERE path = ?", (old_path,),
            )
            self._conn.execute(
                """INSERT INTO indexed_files
                    (path, source_root, content_hash, file_size, mtime,
                     chunk_count, status, error_msg, indexed_at,
                     updated_at, include_rag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)""",
                (new_path, new_source_root, rec["content_hash"],
                 rec["file_size"], rec["mtime"], rec["chunk_count"],
                 rec["status"], rec["error_msg"], rec["indexed_at"],
                 rec["include_rag"]),
            )
            # Move include_rag metadata if present
            meta = self._conn.execute(
                "SELECT * FROM file_metadata WHERE path = ?", (old_path,),
            ).fetchone()
            if meta:
                self._conn.execute(
                    "DELETE FROM file_metadata WHERE path = ?", (old_path,),
                )
                self._conn.execute(
                    """INSERT INTO file_metadata (path, include_rag, updated_at)
                    VALUES (?, ?, datetime('now'))""",
                    (new_path, meta["include_rag"]),
                )
            self._conn.commit()
            return True

    def remove_file(self, path: str):
        """Remove a file from tracking and metadata."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM indexed_files WHERE path = ?", (path,),
            )
            self._conn.execute(
                "DELETE FROM file_metadata WHERE path = ?", (path,),
            )
            self._conn.commit()

    def remove_files_not_in(self, current_paths: set[str]) -> list[str]:
        """Remove files no longer on disk. Returns removed paths.

        Cleans both indexed_files and file_metadata to prevent ghost entries.
        """
        with self._lock:
            # Collect paths from both tables
            all_tracked = self._conn.execute(
                """SELECT path FROM indexed_files
                UNION
                SELECT path FROM file_metadata"""
            ).fetchall()
            removed = [
                r["path"] for r in all_tracked
                if r["path"] not in current_paths
            ]
            if removed:
                self._conn.executemany(
                    "DELETE FROM indexed_files WHERE path = ?",
                    [(p,) for p in removed],
                )
                self._conn.executemany(
                    "DELETE FROM file_metadata WHERE path = ?",
                    [(p,) for p in removed],
                )
                self._conn.commit()
            return removed

    # --- Stats ---

    def get_stats(self) -> dict:
        """Return summary statistics for the UI."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT status, COUNT(*) as cnt,
                          COALESCE(SUM(chunk_count), 0) as chunks
                FROM indexed_files GROUP BY status"""
            ).fetchall()
            stats = {
                "total_files": 0, "total_chunks": 0,
                "complete": 0, "pending": 0,
                "indexing": 0, "error": 0,
            }
            for r in rows:
                stats[r["status"]] = r["cnt"]
                stats["total_files"] += r["cnt"]
                stats["total_chunks"] += r["chunks"]
            return stats

    def clear_hashes(self):
        """Reset all content hashes so every file is treated as changed."""
        with self._lock:
            self._conn.execute(
                "UPDATE indexed_files SET content_hash = '', "
                "updated_at = datetime('now') "
                "WHERE include_rag = 1"
            )
            self._conn.commit()
            logger.info("All content hashes cleared (force reindex)")

    def clear(self):
        """Reset indexing state but preserve user metadata.

        Used when switching embedding models.  Deletes all indexing records
        from indexed_files so every file is re-scanned, but file_metadata
        (tags, include_rag) is kept intact.
        """
        with self._lock:
            self._conn.execute("DELETE FROM indexed_files")
            self._conn.commit()
            logger.info("Tracking database cleared (file_metadata preserved)")

    def file_count(self) -> int:
        """Return the total number of tracked files."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM indexed_files"
            ).fetchone()
            return row["cnt"]
