"""SQLite persistence for file tags — owned by the tags plugin."""

import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS file_tags (
    path       TEXT PRIMARY KEY,
    tags       TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class TagDB:
    """Persists file-level tags in a plugin-owned SQLite database."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "tags.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_CREATE_SQL)
        self._lock = threading.Lock()
        self._conn.commit()
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
        with self._lock:
            paths: set[str] = set()
            for tag in tags:
                rows = self._conn.execute(
                    "SELECT path FROM file_tags "
                    "WHERE tags = ? OR tags LIKE ? OR tags LIKE ? OR tags LIKE ?",
                    (tag, f"{tag},%", f"%, {tag},%", f"%, {tag}"),
                ).fetchall()
                for r in rows:
                    paths.add(r["path"])
            return paths

    def is_empty(self) -> bool:
        """Check if the database has any records."""
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM file_tags").fetchone()
        return row["n"] == 0

    # -- Lifecycle -----------------------------------------------------------

    def close(self) -> None:
        self._conn.close()
