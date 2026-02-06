"""SQLite tracking database for the indexing pipeline.

SQLite is the source of truth for *what's indexed*.
ChromaDB remains the source of truth for *the actual vectors*.
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

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
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_files_source_root
    ON indexed_files(source_root);
CREATE INDEX IF NOT EXISTS idx_files_status
    ON indexed_files(status);
"""


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
        self._init_schema()
        logger.info("TrackingDB opened: %s", db_path)

    def _init_schema(self):
        """Create tables if they don't exist."""
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

    def close(self):
        """Close the database connection."""
        self._conn.close()

    # --- Single-file queries ---

    def get_file(self, path: str) -> dict | None:
        """Return the tracked state for a single file, or None."""
        row = self._conn.execute(
            "SELECT * FROM indexed_files WHERE path = ?", (path,),
        ).fetchone()
        return dict(row) if row else None

    def get_hash(self, path: str) -> str | None:
        """Return the stored content_hash for a file, or None."""
        row = self._conn.execute(
            "SELECT content_hash FROM indexed_files WHERE path = ?",
            (path,),
        ).fetchone()
        return row["content_hash"] if row else None

    # --- Bulk queries ---

    def get_all_files(self) -> list[dict]:
        """Return all tracked files ordered by path."""
        rows = self._conn.execute(
            "SELECT * FROM indexed_files ORDER BY path"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_hash_map(self) -> dict[str, str]:
        """Return {path: content_hash} for all tracked files."""
        rows = self._conn.execute(
            "SELECT path, content_hash FROM indexed_files"
        ).fetchall()
        return {r["path"]: r["content_hash"] for r in rows}

    def get_files_by_status(self, status: str) -> list[dict]:
        """Return files with a given status."""
        rows = self._conn.execute(
            "SELECT * FROM indexed_files WHERE status = ?",
            (status,),
        ).fetchall()
        return [dict(r) for r in rows]

    def recover_incomplete(self) -> list[str]:
        """Return paths stuck in 'indexing' status (crashed mid-index)."""
        rows = self._conn.execute(
            "SELECT path FROM indexed_files WHERE status = 'indexing'"
        ).fetchall()
        return [r["path"] for r in rows]

    # --- Mutations ---

    def upsert_file(
        self, path: str, source_root: str,
        content_hash: str, file_size: int, mtime: float, *,
        status: str = "pending", chunk_count: int = 0,
    ):
        """Insert or update a file's tracking record."""
        self._conn.execute(
            """INSERT INTO indexed_files
                (path, source_root, content_hash, file_size, mtime,
                 chunk_count, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
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
             chunk_count, status),
        )
        self._conn.commit()

    def mark_indexing(self, path: str):
        """Set status='indexing' as a crash recovery marker."""
        self._conn.execute(
            """UPDATE indexed_files
            SET status = 'indexing', updated_at = datetime('now')
            WHERE path = ?""",
            (path,),
        )
        self._conn.commit()

    def mark_complete(self, path: str, chunk_count: int):
        """Set status='complete' with chunk count and timestamp."""
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
        self._conn.execute(
            """UPDATE indexed_files
            SET status = 'error', error_msg = ?,
                updated_at = datetime('now')
            WHERE path = ?""",
            (error_msg, path),
        )
        self._conn.commit()

    def exclude_file(self, path: str):
        """Mark a file as excluded from RAG."""
        self._conn.execute(
            """UPDATE indexed_files
            SET status = 'excluded', chunk_count = 0,
                updated_at = datetime('now')
            WHERE path = ?""",
            (path,),
        )
        self._conn.commit()

    def include_file(self, path: str):
        """Mark an excluded file for re-indexing."""
        self._conn.execute(
            """UPDATE indexed_files
            SET status = 'pending',
                updated_at = datetime('now')
            WHERE path = ? AND status = 'excluded'""",
            (path,),
        )
        self._conn.commit()

    def get_excluded_paths(self) -> set[str]:
        """Return paths of all excluded files."""
        rows = self._conn.execute(
            "SELECT path FROM indexed_files WHERE status = 'excluded'"
        ).fetchall()
        return {r["path"] for r in rows}

    def remove_file(self, path: str):
        """Remove a file from tracking."""
        self._conn.execute(
            "DELETE FROM indexed_files WHERE path = ?", (path,),
        )
        self._conn.commit()

    def remove_files_not_in(self, current_paths: set[str]) -> list[str]:
        """Remove files no longer on disk. Returns removed paths."""
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
        rows = self._conn.execute(
            """SELECT status, COUNT(*) as cnt,
                      COALESCE(SUM(chunk_count), 0) as chunks
            FROM indexed_files GROUP BY status"""
        ).fetchall()
        stats = {
            "total_files": 0, "total_chunks": 0,
            "complete": 0, "pending": 0,
            "indexing": 0, "error": 0, "excluded": 0,
        }
        for r in rows:
            stats[r["status"]] = r["cnt"]
            stats["total_files"] += r["cnt"]
            stats["total_chunks"] += r["chunks"]
        return stats

    def clear(self):
        """Delete all file tracking records (used when switching models)."""
        self._conn.execute("DELETE FROM indexed_files")
        self._conn.commit()
        logger.info("Tracking database cleared")

    def file_count(self) -> int:
        """Return the total number of tracked files."""
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM indexed_files"
        ).fetchone()
        return row["cnt"]
