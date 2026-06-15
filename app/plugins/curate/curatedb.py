"""SQLite persistence for curate drafts — owned by the curate plugin.

A *draft* is a bucket-C candidate from the analyze–match–codify loop: a
practiced-but-uncodified pattern an agent harvested from a source (a
codebase, a bucket) and wants to graduate into the canonical corpus. The
draft store is the one piece of genuinely new state curate adds — mdkb
has no "draft" status distinct from a live writable source.

Status lifecycle: ``draft`` → ``graduated`` | ``rejected``. The two human
gates (drafting is opt-in; a curator graduates each candidate by hand)
live above this store; the store just records the state.
"""

import logging
import sqlite3
import threading
import uuid
from pathlib import Path

from app.storage.migrations import run_migrations

logger = logging.getLogger(__name__)

# Allowed status values. Drafts start as ``draft`` and move to a terminal
# state via graduate()/reject(); terminal rows are kept for provenance.
STATUSES = ("draft", "graduated", "rejected")

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS drafts (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    body_md       TEXT NOT NULL,
    taxonomy_slot TEXT NOT NULL DEFAULT '',
    source_type   TEXT NOT NULL DEFAULT '',
    source_ref    TEXT NOT NULL DEFAULT '',
    run_id        TEXT,
    status        TEXT NOT NULL DEFAULT 'draft',
    graduated_path TEXT,
    reject_reason TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts(status);
"""

_MIGRATIONS: list[tuple[int, str, str]] = []


class CurateDB:
    """Persists curate drafts in a plugin-owned SQLite database."""

    _UPDATABLE_COLUMNS = frozenset({
        "title", "body_md", "taxonomy_slot", "source_type", "source_ref",
        "run_id", "status", "graduated_path", "reject_reason",
    })

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "curate.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_CREATE_SQL)
        run_migrations(self._conn, _MIGRATIONS, db_label="CurateDB")
        self._lock = threading.Lock()
        self._conn.commit()
        logger.info("CurateDB opened: %s", db_path)

    # -- Write operations ----------------------------------------------------

    def create(
        self,
        *,
        title: str,
        body_md: str,
        taxonomy_slot: str = "",
        source_type: str = "",
        source_ref: str = "",
        run_id: str | None = None,
    ) -> dict:
        """Insert a new draft (status=draft). Returns the created row."""
        draft_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._conn.execute(
                """INSERT INTO drafts
                   (id, title, body_md, taxonomy_slot, source_type, source_ref, run_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (draft_id, title, body_md, taxonomy_slot, source_type, source_ref, run_id),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM drafts WHERE id = ?", (draft_id,)
            ).fetchone()
        return dict(row)

    def update(self, draft_id: str, **fields) -> bool:
        """Update allowed columns on a draft and bump ``updated_at``.

        Only keys in :attr:`_UPDATABLE_COLUMNS` are accepted; an unknown key
        raises ``ValueError`` so SQL cannot be composed from caller-controlled
        names. ``id`` and ``created_at`` are immutable.
        """
        if not fields:
            return False
        bad = set(fields) - self._UPDATABLE_COLUMNS
        if bad:
            raise ValueError(f"Unknown draft columns: {sorted(bad)}")
        cols = list(fields)
        set_clause = ", ".join(f"{c} = ?" for c in cols)
        values = [fields[c] for c in cols] + [draft_id]
        with self._lock:
            cursor = self._conn.execute(
                f"UPDATE drafts SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def delete(self, draft_id: str) -> bool:
        """Delete a draft by ID."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM drafts WHERE id = ?", (draft_id,)
            )
            self._conn.commit()
        return cursor.rowcount > 0

    # -- Read operations -----------------------------------------------------

    def get(self, draft_id: str) -> dict | None:
        """Get a single draft by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM drafts WHERE id = ?", (draft_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_all(self, status: str | None = None) -> list[dict]:
        """Return drafts, optionally filtered by status, newest-first."""
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM drafts WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM drafts ORDER BY created_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def counts_by_status(self) -> dict[str, int]:
        """Return a {status: count} map across all drafts."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT status, COUNT(*) AS n FROM drafts GROUP BY status"
            ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    # -- Lifecycle -----------------------------------------------------------

    def close(self) -> None:
        self._conn.close()
