"""SQLite tracking database for the indexing pipeline.

SQLite is the source of truth for *what's indexed*.
ChromaDB remains the source of truth for *the actual vectors*.
"""

import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 3

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

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


class TrackingDB:
    """Tracks indexed file states in SQLite."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "mdkb.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(db_path), check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        self._init_schema()
        logger.info("TrackingDB opened: %s", db_path)

    def _init_schema(self):
        """Create tables if they don't exist, then run migrations."""
        self._conn.executescript(_CREATE_SQL)
        row = self._conn.execute(
            "SELECT version FROM schema_version LIMIT 1"
        ).fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            self._conn.commit()
        else:
            current = row["version"]
            if current < 2:
                _migrate_v1_to_v2(self._conn)
            if current < 3:
                _migrate_v2_to_v3(self._conn)
            if current < SCHEMA_VERSION:
                self._conn.execute(
                    "UPDATE schema_version SET version = ?",
                    (SCHEMA_VERSION,),
                )
                self._conn.commit()

    def close(self):
        """Close the database connection."""
        with self._lock:
            self._conn.close()

    # --- Single-file queries ---

    def get_file(self, path: str) -> dict | None:
        """Return the tracked state for a single file, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM indexed_files WHERE path = ?", (path,),
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
        """Return tracked files ordered by path, with optional pagination."""
        with self._lock:
            sql = "SELECT * FROM indexed_files ORDER BY path"
            params: list = []
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                params = [limit, offset]
            rows = self._conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_paths_for_tags(self, tags: set[str]) -> set[str]:
        """Return file paths that have any of the given tags (SQL-level filter).

        Uses LIKE queries per tag to avoid full-table Python iteration.
        """
        if not tags:
            return set()
        with self._lock:
            paths: set[str] = set()
            for tag in tags:
                # Match exact tag in comma-separated list
                rows = self._conn.execute(
                    "SELECT path FROM indexed_files "
                    "WHERE tags = ? OR tags LIKE ? OR tags LIKE ? OR tags LIKE ?",
                    (tag, f"{tag},%", f"%, {tag},%", f"%, {tag}"),
                ).fetchall()
                for r in rows:
                    paths.add(r["path"])
            return paths

    def get_hash_map(self) -> dict[str, str]:
        """Return {path: content_hash} for all tracked files."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT path, content_hash FROM indexed_files"
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
                    content_hash = '', updated_at = datetime('now')
                WHERE status = 'indexing'"""
            )
            self._conn.commit()
            return cursor.rowcount

    # --- Mutations ---

    def upsert_file(
        self, path: str, source_root: str,
        content_hash: str, file_size: int, mtime: float, *,
        status: str = "pending", chunk_count: int = 0,
        tags: str = "",
    ):
        """Insert or update a file's tracking record."""
        with self._lock:
            self._conn.execute(
                """INSERT INTO indexed_files
                    (path, source_root, content_hash, file_size, mtime,
                     chunk_count, status, tags, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(path) DO UPDATE SET
                    source_root = excluded.source_root,
                    content_hash = excluded.content_hash,
                    file_size = excluded.file_size,
                    mtime = excluded.mtime,
                    chunk_count = excluded.chunk_count,
                    status = excluded.status,
                    tags = excluded.tags,
                    error_msg = NULL,
                    indexed_at = CASE
                        WHEN excluded.status = 'complete'
                        THEN datetime('now')
                        ELSE indexed_files.indexed_at
                    END,
                    updated_at = datetime('now')
                """,
                (path, source_root, content_hash, file_size, mtime,
                 chunk_count, status, tags),
            )
            self._conn.commit()

    def update_tags(self, path: str, tags: str):
        """Update only the tags field for a file."""
        with self._lock:
            self._conn.execute(
                "UPDATE indexed_files SET tags = ?, updated_at = datetime('now') WHERE path = ?",
                (tags, path),
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
        """Set status='error' with error message."""
        with self._lock:
            self._conn.execute(
                """UPDATE indexed_files
                SET status = 'error', error_msg = ?,
                    updated_at = datetime('now')
                WHERE path = ?""",
                (error_msg, path),
            )
            self._conn.commit()

    def set_include_rag(self, path: str, include: bool):
        """Toggle whether a file is included in RAG search results."""
        with self._lock:
            self._conn.execute(
                """UPDATE indexed_files
                SET include_rag = ?, updated_at = datetime('now')
                WHERE path = ?""",
                (1 if include else 0, path),
            )
            self._conn.commit()

    def get_rag_excluded_paths(self) -> set[str]:
        """Return paths of files excluded from RAG search."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT path FROM indexed_files WHERE include_rag = 0"
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
            self._conn.commit()
            return True

    def remove_file(self, path: str):
        """Remove a file from tracking."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM indexed_files WHERE path = ?", (path,),
            )
            self._conn.commit()

    def remove_files_not_in(self, current_paths: set[str]) -> list[str]:
        """Remove files no longer on disk. Returns removed paths."""
        with self._lock:
            all_tracked = self._conn.execute(
                "SELECT path FROM indexed_files"
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
        """Delete all file tracking records (used when switching models)."""
        with self._lock:
            self._conn.execute("DELETE FROM indexed_files")
            self._conn.commit()
            logger.info("Tracking database cleared")

    def file_count(self) -> int:
        """Return the total number of tracked files."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM indexed_files"
            ).fetchone()
            return row["cnt"]
