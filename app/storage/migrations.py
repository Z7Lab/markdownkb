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


def run_migrations(
    conn: sqlite3.Connection,
    migrations: list[Migration],
    db_label: str = "",
) -> None:
    """Apply any migrations whose version > current PRAGMA user_version.

    SQL-string bodies are applied with a single ``execute`` — ``ALTER``
    statements that would fail on a freshly created table (because the
    column already exists in ``CREATE TABLE``) are swallowed.

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
            except sqlite3.OperationalError:
                logger.debug(
                    "%s migration %d skipped (already present): %s",
                    db_label or "DB", version, description,
                )
    # PRAGMA can't be parameterised; target is len(migrations), code-controlled.
    conn.execute(f"PRAGMA user_version = {int(target)}")
    conn.commit()
