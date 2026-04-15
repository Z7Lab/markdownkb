"""Canonical schema-migration runner for SQLite databases.

Every SQLite database in mdkb tracks its schema version in ``PRAGMA
user_version`` and applies an ordered list of migrations on startup.
See ``docs/explanation/versioning-and-upgrades.md`` for the full
discipline (forward-only, idempotent, sequential numbering, etc.).
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

# (version, description, sql) — version numbers start at 1 and are sequential.
Migration = tuple[int, str, str]


def run_migrations(
    conn: sqlite3.Connection,
    migrations: list[Migration],
    db_label: str = "",
) -> None:
    """Apply any migrations whose version > current PRAGMA user_version.

    Each ``ALTER`` is wrapped in a try/except for ``sqlite3.OperationalError``
    so reapplying a migration on a fresh database (where the column already
    exists in ``CREATE TABLE``) is a no-op.
    """
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    target = len(migrations)
    if current >= target:
        return
    for version, description, sql in migrations:
        if version <= current:
            continue
        try:
            conn.execute(sql)
            logger.info("%s migration %d applied: %s", db_label or "DB", version, description)
        except sqlite3.OperationalError:
            logger.debug(
                "%s migration %d skipped (already present): %s",
                db_label or "DB", version, description,
            )
    # PRAGMA can't be parameterised; target is len(migrations), code-controlled.
    conn.execute(f"PRAGMA user_version = {int(target)}")
    conn.commit()
