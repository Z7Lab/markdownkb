"""SQLite persistence for search history."""

import json
import logging
import sqlite3
import threading
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS searches (
    id             TEXT PRIMARY KEY,
    query          TEXT NOT NULL,
    folder         TEXT,
    tag            TEXT,
    summary        TEXT,
    result_paths   TEXT,
    result_count   INTEGER,
    last_viewed_at TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "add summary column to searches", "ALTER TABLE searches ADD COLUMN summary TEXT"),
    (2, "add result_paths column to searches", "ALTER TABLE searches ADD COLUMN result_paths TEXT"),
    (3, "add result_count column to searches", "ALTER TABLE searches ADD COLUMN result_count INTEGER"),
    (4, "add last_viewed_at column to searches", "ALTER TABLE searches ADD COLUMN last_viewed_at TEXT"),
    (5, "add result_details column to searches", "ALTER TABLE searches ADD COLUMN result_details TEXT"),
    (6, "add result_data column to searches", "ALTER TABLE searches ADD COLUMN result_data TEXT"),
    (7, "add parent_id column to searches", "ALTER TABLE searches ADD COLUMN parent_id TEXT"),
    (8, "add source column to searches", "ALTER TABLE searches ADD COLUMN source TEXT DEFAULT 'web'"),
]


class SearchDB:
    """Persists search history in SQLite."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "searches.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_CREATE_SQL)
        self._lock = threading.Lock()
        self._run_migrations()
        self._conn.commit()
        logger.info("SearchDB opened: %s", db_path)

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
        with self._lock:
            self._conn.close()

    def save_search(
        self,
        query: str,
        folder: str | None = None,
        tag: str | None = None,
        result_paths: list[str] | None = None,
        result_count: int | None = None,
        result_details: list[dict] | None = None,
        result_data: list[dict] | None = None,
        parent_id: str | None = None,
        source: str = "web",
    ) -> str:
        """Save a new search with result metadata and full results.

        Args:
            result_details: List of dicts with {path, score} for each result
            result_data: Full grouped results with snippets (preserves original view)
            parent_id: Root search ID linking re-queries into a version chain
            source: Origin of the search — "web" (UI) or "agent" (MCP)
        """
        search_id = uuid.uuid4().hex[:12]
        result_paths_json = json.dumps(result_paths) if result_paths else None
        result_details_json = json.dumps(result_details) if result_details else None
        result_data_json = json.dumps(result_data) if result_data else None
        with self._lock:
            self._conn.execute(
                """INSERT INTO searches
                   (id, query, folder, tag, result_paths, result_count, result_details, result_data, parent_id, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (search_id, query, folder, tag, result_paths_json, result_count, result_details_json, result_data_json, parent_id, source),
            )
            self._conn.commit()
        return search_id

    def list_searches(self, *, offset: int = 0, limit: int | None = None) -> list[dict]:
        with self._lock:
            sql = "SELECT * FROM searches ORDER BY created_at DESC"
            params: list = []
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                params = [limit, offset]
            rows = self._conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def search_count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) as cnt FROM searches").fetchone()
            return row["cnt"]

    def get_search(self, search_id: str) -> dict | None:
        """Get a search by ID, parse JSON fields."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM searches WHERE id = ?", (search_id,)
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            corrupt_fields: list[str] = []
            # Parse JSON result_paths
            for field in ("result_paths", "result_details", "result_data"):
                raw = result.get(field)
                if raw:
                    try:
                        result[field] = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.error(
                            "Corrupt %s JSON for search %s — returning empty list "
                            "(raw data preserved in DB for manual recovery)",
                            field, search_id,
                        )
                        result[field] = []
                        corrupt_fields.append(field)
                else:
                    result[field] = []
            if corrupt_fields:
                result["_corrupt_fields"] = corrupt_fields
                result["_data_corrupt"] = True
            return result

    def get_search_versions(self, search_id: str) -> list[dict]:
        """Get all versions of a search chain (lightweight metadata only).

        Resolves the root of the chain, then returns all searches with
        that root (original + all re-queries), ordered by creation time.
        """
        with self._lock:
            # Determine root ID
            row = self._conn.execute(
                "SELECT id, parent_id FROM searches WHERE id = ?", (search_id,)
            ).fetchone()
            if not row:
                return []
            root_id = row["parent_id"] or row["id"]

            # Get all versions in this chain
            rows = self._conn.execute(
                "SELECT id, query, result_count, summary, created_at, parent_id "
                "FROM searches WHERE id = ? OR parent_id = ? ORDER BY created_at",
                (root_id, root_id),
            ).fetchall()
            return [dict(r) for r in rows]

    def mark_viewed(self, search_id: str):
        """Update last_viewed_at timestamp when loading a historical search."""
        with self._lock:
            self._conn.execute(
                "UPDATE searches SET last_viewed_at = datetime('now') WHERE id = ?",
                (search_id,),
            )
            self._conn.commit()

    def update_summary(self, search_id: str, summary: str):
        """Save AI-generated summary for a search."""
        with self._lock:
            self._conn.execute(
                "UPDATE searches SET summary = ? WHERE id = ?",
                (summary, search_id),
            )
            self._conn.commit()

    def rename_search(self, search_id: str, query: str) -> bool:
        """Rename a search's query text. Returns True if it existed."""
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE searches SET query = ? WHERE id = ?",
                (query, search_id),
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def delete_search(self, search_id: str):
        with self._lock:
            self._conn.execute("DELETE FROM searches WHERE id = ?", (search_id,))
            self._conn.commit()

    def clear_all(self):
        with self._lock:
            self._conn.execute("DELETE FROM searches")
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
