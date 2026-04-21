"""Canonical schema-migration runner for SQLite databases.

Every SQLite database in mdkb tracks its schema version in ``PRAGMA
user_version`` and applies an ordered list of migrations on startup.
See ``docs/explanation/versioning-and-upgrades.md`` for the full
discipline (forward-only, idempotent, sequential numbering, etc.).
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Callable, Union

logger = logging.getLogger(__name__)

# A migration is (version, description, body). ``body`` may be a SQL string
# (applied with a single ``execute``) or a callable that receives the
# connection and performs multi-statement or data-transform work.
MigrationBody = Union[str, Callable[[sqlite3.Connection], None]]
Migration = tuple[int, str, MigrationBody]

# SQLite OperationalError message fragments that indicate "the migration
# target already exists" — safe to skip for idempotent ALTERs. Anything
# outside this list is treated as a genuine failure.
_IDEMPOTENT_ERROR_FRAGMENTS = (
    "duplicate column name",
    "already exists",
)


def _is_already_exists_error(exc: sqlite3.OperationalError) -> bool:
    """Return True if *exc* indicates an already-applied migration."""
    msg = str(exc).lower()
    return any(fragment in msg for fragment in _IDEMPOTENT_ERROR_FRAGMENTS)


def run_migrations(
    conn: sqlite3.Connection,
    migrations: list[Migration],
    db_label: str = "",
) -> None:
    """Apply any migrations whose version > current PRAGMA user_version.

    SQL-string bodies are applied with a single ``execute`` — ``ALTER``
    statements that would fail because the target already exists (column
    already present from a fresh ``CREATE TABLE``, or index/table that was
    re-created) are swallowed. Genuine errors (disk full, corrupt DB,
    syntax) are re-raised so they surface loudly.

    Callable bodies receive the connection and are expected to be
    idempotent; any existing ``PRAGMA table_info`` / ``sqlite_master``
    guards inside them continue to work.
    """
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    target = len(migrations)
    if current >= target:
        return
    for version, description, body in migrations:
        if version <= current:
            continue
        if callable(body):
            body(conn)
            logger.info("%s migration %d applied: %s", db_label or "DB", version, description)
        else:
            try:
                conn.execute(body)
                logger.info("%s migration %d applied: %s", db_label or "DB", version, description)
            except sqlite3.OperationalError as e:
                if _is_already_exists_error(e):
                    logger.debug(
                        "%s migration %d skipped (already present): %s",
                        db_label or "DB", version, description,
                    )
                else:
                    logger.error(
                        "%s migration %d failed: %s — %s",
                        db_label or "DB", version, description, e,
                    )
                    raise
    # PRAGMA can't be parameterised; target is len(migrations), code-controlled.
    conn.execute(f"PRAGMA user_version = {int(target)}")
    conn.commit()
