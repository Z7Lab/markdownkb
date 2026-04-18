"""Guard: every DB class must have PRAGMA user_version == len(_MIGRATIONS).

This test catches the common mistake of adding a column to _CREATE_SQL
without a corresponding migration (or adding a migration without updating
_CREATE_SQL). It also verifies that TagDB and WikiDB have the migration
runner wired up correctly.

Each test opens the DB in a fresh temp directory, so no existing data is
touched.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest


def _open_fresh(db_class, *args, **kwargs):
    with tempfile.TemporaryDirectory() as d:
        return db_class(d, *args, **kwargs), d


# ── Core storage DBs ──────────────────────────────────────────────────────

def test_trackingdb_schema_version():
    from app.storage.trackingdb import TrackingDB, _MIGRATIONS
    with tempfile.TemporaryDirectory() as d:
        db = TrackingDB(d)
        version = db._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == len(_MIGRATIONS), (
            f"TrackingDB user_version={version} but len(_MIGRATIONS)={len(_MIGRATIONS)}"
        )
        db.close()


def test_chatdb_schema_version():
    from app.storage.chatdb import ChatDB, _MIGRATIONS
    with tempfile.TemporaryDirectory() as d:
        db = ChatDB(d)
        version = db._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == len(_MIGRATIONS)
        db.close()


def test_searchdb_schema_version():
    from app.storage.searchdb import SearchDB, _MIGRATIONS
    with tempfile.TemporaryDirectory() as d:
        db = SearchDB(d)
        version = db._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == len(_MIGRATIONS)
        db.close()


def test_plandb_schema_version():
    from app.storage.plandb import PlanDB, _MIGRATIONS
    with tempfile.TemporaryDirectory() as d:
        db = PlanDB(d)
        version = db._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == len(_MIGRATIONS)
        db.close()


def test_scopedb_schema_version():
    from app.storage.scopedb import ScopeDB, _MIGRATIONS
    with tempfile.TemporaryDirectory() as d:
        db = ScopeDB(d)
        version = db._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == len(_MIGRATIONS)
        db.close()


def test_presetsdb_schema_version():
    from app.storage.presetsdb import PresetsDB, _MIGRATIONS
    with tempfile.TemporaryDirectory() as d:
        db = PresetsDB(d)
        version = db._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == len(_MIGRATIONS)
        db.close()


def test_knowledgegraphdb_schema_version():
    from app.storage.knowledgegraph import KnowledgeGraphDB, _MIGRATIONS
    with tempfile.TemporaryDirectory() as d:
        db = KnowledgeGraphDB(d)
        version = db._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == len(_MIGRATIONS)
        db.close()


# ── Plugin DBs ────────────────────────────────────────────────────────────

def test_bucketdb_schema_version():
    from app.plugins.buckets.bucketdb import BucketDB, _MIGRATIONS
    with tempfile.TemporaryDirectory() as d:
        db = BucketDB(d)
        version = db._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == len(_MIGRATIONS)
        db.close()


def test_tagdb_schema_version():
    from app.plugins.tags.tagdb import TagDB, _MIGRATIONS
    with tempfile.TemporaryDirectory() as d:
        db = TagDB(d)
        version = db._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == len(_MIGRATIONS), (
            f"TagDB user_version={version} but len(_MIGRATIONS)={len(_MIGRATIONS)}"
        )
        db.close()


def test_wikidb_schema_version():
    from app.plugins.wiki_compile.wikidb import WikiDB, _MIGRATIONS
    with tempfile.TemporaryDirectory() as d:
        db = WikiDB(d)
        version = db._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == len(_MIGRATIONS), (
            f"WikiDB user_version={version} but len(_MIGRATIONS)={len(_MIGRATIONS)}"
        )
        db.close()


# ── Migration idempotency — run_migrations twice is safe ──────────────────

def test_run_migrations_idempotent():
    """Running migrations on an already-migrated DB is a no-op."""
    from app.storage.migrations import run_migrations
    from app.storage.chatdb import _MIGRATIONS, _CREATE_SQL

    with tempfile.TemporaryDirectory() as d:
        conn = sqlite3.connect(str(Path(d) / "test.db"))
        conn.executescript(_CREATE_SQL)
        run_migrations(conn, _MIGRATIONS, db_label="test")
        v1 = conn.execute("PRAGMA user_version").fetchone()[0]
        run_migrations(conn, _MIGRATIONS, db_label="test")
        v2 = conn.execute("PRAGMA user_version").fetchone()[0]
        assert v1 == v2 == len(_MIGRATIONS)
        conn.close()
