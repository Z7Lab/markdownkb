"""SQLite persistence for file tags — owned by the tags plugin."""

import logging
import sqlite3
import threading
from pathlib import Path

from app.storage.migrations import Migration, run_migrations

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS file_tags (
    path       TEXT PRIMARY KEY,
    tags       TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_MIGRATIONS: list[Migration] = []


class TagDB:
    """Persists file-level tags in a plugin-owned SQLite database."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "tags.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_CREATE_SQL)
        run_migrations(self._conn, _MIGRATIONS, db_label="TagDB")
        self._lock = threading.Lock()
        logger.info("TagDB opened: %s", db_path)

    # -- Write operations ----------------------------------------------------

    def update_tags(self, path: str, tags: str) -> None:
        """Upsert tags for a file path."""
        with self._lock:
            self._conn.execute(
                """INSERT INTO file_tags (path, tags, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(path) DO UPDATE SET
                    tags = excluded.tags,
                    updated_at = excluded.updated_at""",
                (path, tags),
            )
            self._conn.commit()

    def remove_file(self, path: str) -> None:
        """Remove a file's tag record."""
        with self._lock:
            self._conn.execute("DELETE FROM file_tags WHERE path = ?", (path,))
            self._conn.commit()

    def rename_file(self, old_path: str, new_path: str) -> None:
        """Update path when a file is renamed/moved."""
        with self._lock:
            self._conn.execute(
                "UPDATE file_tags SET path = ?, updated_at = datetime('now') WHERE path = ?",
                (new_path, old_path),
            )
            self._conn.commit()

    def clear(self) -> None:
        """Remove all tag records."""
        with self._lock:
            self._conn.execute("DELETE FROM file_tags")
            self._conn.commit()
            logger.info("TagDB cleared")

    # -- Read operations -----------------------------------------------------

    def get_tags(self, path: str) -> str:
        """Return tags for a single file, or empty string if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT tags FROM file_tags WHERE path = ?", (path,),
            ).fetchone()
        return row["tags"] if row else ""

    def get_all_tags(self) -> list[str]:
        """Return sorted list of all unique tags across all files."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT tags FROM file_tags WHERE tags != ''"
            ).fetchall()
        tags: set[str] = set()
        for row in rows:
            for t in row["tags"].split(","):
                t = t.strip()
                if t:
                    tags.add(t)
        return sorted(tags)

    def get_all_tags_with_counts(self) -> list[dict]:
        """Return sorted list of all unique tags with file counts."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT tags FROM file_tags WHERE tags != ''"
            ).fetchall()
        counts: dict[str, int] = {}
        for row in rows:
            for t in row["tags"].split(","):
                t = t.strip()
                if t:
                    counts[t] = counts.get(t, 0) + 1
        return [{"tag": t, "count": counts[t]} for t in sorted(counts)]

    def get_all_file_tags(self) -> list[dict]:
        """Return all (path, tags) rows for enriching file listings."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT path, tags FROM file_tags WHERE tags != ''"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_paths_for_tags(self, tags: set[str]) -> set[str]:
        """Return file paths that have any of the given tags (OR logic)."""
        if not tags:
            return set()
        # Build a single query with OR clauses for all tags
        conditions = []
        params: list[str] = []
        for tag in tags:
            conditions.append(
                "(tags = ? OR tags LIKE ? OR tags LIKE ? OR tags LIKE ?)"
            )
            params.extend([tag, f"{tag},%", f"%, {tag},%", f"%, {tag}"])
        where_clause = " OR ".join(conditions)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT DISTINCT path FROM file_tags WHERE {where_clause}",
                params,
            ).fetchall()
        return {r["path"] for r in rows}

    def get_all_paths(self) -> set[str]:
        """Return all file paths that have tag entries."""
        with self._lock:
            rows = self._conn.execute("SELECT path FROM file_tags").fetchall()
        return {r["path"] for r in rows}

    def is_empty(self) -> bool:
        """Check if the database has any records."""
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM file_tags").fetchone()
        return row["n"] == 0

    # -- Lifecycle -----------------------------------------------------------

    def close(self) -> None:
        self._conn.close()
