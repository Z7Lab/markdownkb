"""Knowledge graph storage — entities and typed relationships.

Separate SQLite database (markdownkb_kg.db) so KG data survives embedding
model switches (which only clear ChromaDB and the tracking table).
"""

import hashlib
import logging
import sqlite3
import threading
from collections import deque
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS kg_entities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    display_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source_path TEXT NOT NULL,
    chunk_hash  TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(name, entity_type, source_path)
);

CREATE TABLE IF NOT EXISTS kg_relationships (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    source_entity_id  INTEGER NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
    target_entity_id  INTEGER NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
    rel_type          TEXT NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    confidence        REAL NOT NULL DEFAULT 1.0,
    source_path       TEXT NOT NULL,
    chunk_hash        TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source_entity_id, target_entity_id, rel_type, source_path)
);

CREATE TABLE IF NOT EXISTS kg_extraction_cache (
    chunk_hash   TEXT PRIMARY KEY,
    source_path  TEXT NOT NULL,
    extracted_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_entities_name ON kg_entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON kg_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_source ON kg_entities(source_path);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON kg_relationships(source_path);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON kg_relationships(rel_type);
CREATE INDEX IF NOT EXISTS idx_cache_source ON kg_extraction_cache(source_path);
"""


def chunk_content_hash(content: str) -> str:
    """Compute a stable hash for a chunk's content."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class KnowledgeGraphDB:
    """SQLite storage for knowledge graph entities and relationships."""

    def __init__(self, data_dir: str):
        db_path = Path(data_dir) / "markdownkb_kg.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self):
        with self._lock:
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
        self._conn.close()

    # -- Entity CRUD --

    def upsert_entity(
        self,
        name: str,
        entity_type: str,
        source_path: str,
        display_name: str = "",
        description: str = "",
        chunk_hash: str = "",
    ) -> int:
        """Insert or update an entity. Returns the entity ID."""
        normalized = name.strip().lower()
        display = display_name or name.strip()
        with self._lock:
            self._conn.execute(
                """INSERT INTO kg_entities
                   (name, display_name, entity_type, description, source_path, chunk_hash)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(name, entity_type, source_path) DO UPDATE SET
                       display_name = excluded.display_name,
                       description = excluded.description,
                       chunk_hash = excluded.chunk_hash
                """,
                (normalized, display, entity_type, description, source_path, chunk_hash),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT id FROM kg_entities WHERE name=? AND entity_type=? AND source_path=?",
                (normalized, entity_type, source_path),
            ).fetchone()
            return row["id"]

    def upsert_relationship(
        self,
        source_entity_id: int,
        target_entity_id: int,
        rel_type: str,
        source_path: str,
        description: str = "",
        confidence: float = 1.0,
        chunk_hash: str = "",
    ) -> int:
        """Insert or update a relationship. Returns the relationship ID."""
        with self._lock:
            self._conn.execute(
                """INSERT INTO kg_relationships
                   (source_entity_id, target_entity_id, rel_type, description,
                    confidence, source_path, chunk_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(source_entity_id, target_entity_id, rel_type, source_path)
                   DO UPDATE SET
                       description = excluded.description,
                       confidence = excluded.confidence,
                       chunk_hash = excluded.chunk_hash
                """,
                (source_entity_id, target_entity_id, rel_type, description,
                 confidence, source_path, chunk_hash),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT id FROM kg_relationships "
                "WHERE source_entity_id=? AND target_entity_id=? AND rel_type=? AND source_path=?",
                (source_entity_id, target_entity_id, rel_type, source_path),
            ).fetchone()
            return row["id"]

    # -- Deletion (cascade cleanup) --

    def delete_by_source(self, source_path: str):
        """Delete all entities, relationships, and cache for a source file.

        Relationships are cascade-deleted via FOREIGN KEY ON DELETE CASCADE.
        """
        with self._lock:
            self._conn.execute(
                "DELETE FROM kg_entities WHERE source_path = ?",
                (source_path,),
            )
            # Also clean up relationships that reference this source_path
            # directly (cross-file relationships)
            self._conn.execute(
                "DELETE FROM kg_relationships WHERE source_path = ?",
                (source_path,),
            )
            self._conn.execute(
                "DELETE FROM kg_extraction_cache WHERE source_path = ?",
                (source_path,),
            )
            self._conn.commit()

    def clear(self):
        """Clear all KG data. Only call on explicit user action."""
        with self._lock:
            self._conn.execute("DELETE FROM kg_relationships")
            self._conn.execute("DELETE FROM kg_entities")
            self._conn.execute("DELETE FROM kg_extraction_cache")
            self._conn.commit()
            logger.info("Knowledge graph cleared")

    # -- Cache --

    def is_chunk_extracted(self, chunk_hash: str) -> bool:
        """Check if a chunk has already been extracted."""
        row = self._conn.execute(
            "SELECT 1 FROM kg_extraction_cache WHERE chunk_hash = ?",
            (chunk_hash,),
        ).fetchone()
        return row is not None

    def mark_chunk_extracted(self, chunk_hash: str, source_path: str):
        """Mark a chunk as extracted (for cache)."""
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO kg_extraction_cache
                   (chunk_hash, source_path) VALUES (?, ?)""",
                (chunk_hash, source_path),
            )
            self._conn.commit()

    # -- Queries --

    def get_all_entities(
        self,
        entity_types: list[str] | None = None,
    ) -> list[dict]:
        """Return all entities, optionally filtered by type.

        Entities with the same (name, entity_type) across different source
        files are merged: mention_count is the number of source files,
        source_paths lists all files.
        """
        sql = """
            SELECT name, display_name, entity_type, description,
                   COUNT(DISTINCT source_path) as mention_count,
                   GROUP_CONCAT(DISTINCT source_path) as source_paths
            FROM kg_entities
        """
        params: list = []
        if entity_types:
            placeholders = ",".join("?" * len(entity_types))
            sql += f" WHERE entity_type IN ({placeholders})"
            params.extend(entity_types)
        sql += " GROUP BY name, entity_type"

        rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "name": r["name"],
                "display_name": r["display_name"],
                "entity_type": r["entity_type"],
                "description": r["description"],
                "mention_count": r["mention_count"],
                "source_paths": r["source_paths"].split(",") if r["source_paths"] else [],
            }
            for r in rows
        ]

    def get_all_relationships(
        self,
        rel_types: list[str] | None = None,
    ) -> list[dict]:
        """Return all relationships with entity names resolved."""
        sql = """
            SELECT
                e1.name as source_name, e1.entity_type as source_type,
                e2.name as target_name, e2.entity_type as target_type,
                r.rel_type, r.description, r.confidence, r.source_path
            FROM kg_relationships r
            JOIN kg_entities e1 ON r.source_entity_id = e1.id
            JOIN kg_entities e2 ON r.target_entity_id = e2.id
        """
        params: list = []
        if rel_types:
            placeholders = ",".join("?" * len(rel_types))
            sql += f" WHERE r.rel_type IN ({placeholders})"
            params.extend(rel_types)

        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_entity(self, name: str) -> dict | None:
        """Get a single merged entity by name with all its relationships."""
        normalized = name.strip().lower()
        rows = self._conn.execute(
            "SELECT * FROM kg_entities WHERE name = ?", (normalized,)
        ).fetchall()
        if not rows:
            return None

        # Get all entity IDs for this name
        entity_ids = [r["id"] for r in rows]
        placeholders = ",".join("?" * len(entity_ids))

        # Get outgoing relationships
        outgoing = self._conn.execute(
            f"""SELECT e2.name as target, e2.entity_type as target_type,
                       r.rel_type, r.description, r.confidence
                FROM kg_relationships r
                JOIN kg_entities e2 ON r.target_entity_id = e2.id
                WHERE r.source_entity_id IN ({placeholders})""",
            entity_ids,
        ).fetchall()

        # Get incoming relationships
        incoming = self._conn.execute(
            f"""SELECT e1.name as source, e1.entity_type as source_type,
                       r.rel_type, r.description, r.confidence
                FROM kg_relationships r
                JOIN kg_entities e1 ON r.source_entity_id = e1.id
                WHERE r.target_entity_id IN ({placeholders})""",
            entity_ids,
        ).fetchall()

        return {
            "name": rows[0]["name"],
            "display_name": rows[0]["display_name"],
            "entity_type": rows[0]["entity_type"],
            "description": rows[0]["description"],
            "mention_count": len(rows),
            "source_paths": list({r["source_path"] for r in rows}),
            "outgoing": [dict(r) for r in outgoing],
            "incoming": [dict(r) for r in incoming],
        }

    def find_path(
        self, source_name: str, target_name: str, max_hops: int = 6,
    ) -> list[dict] | None:
        """BFS shortest path between two entities by name.

        Returns a list of steps: [{entity, rel_type, direction}, ...] or None.
        """
        src = source_name.strip().lower()
        tgt = target_name.strip().lower()

        if src == tgt:
            return [{"entity": src, "rel_type": None, "direction": "start"}]

        # Load adjacency into memory for BFS
        rows = self._conn.execute("""
            SELECT DISTINCT e1.name as src, e2.name as tgt, r.rel_type
            FROM kg_relationships r
            JOIN kg_entities e1 ON r.source_entity_id = e1.id
            JOIN kg_entities e2 ON r.target_entity_id = e2.id
        """).fetchall()

        # Build undirected adjacency
        adj: dict[str, list[tuple[str, str, str]]] = {}
        for r in rows:
            s, t, rt = r["src"], r["tgt"], r["rel_type"]
            adj.setdefault(s, []).append((t, rt, "outgoing"))
            adj.setdefault(t, []).append((s, rt, "incoming"))

        if src not in adj:
            return None

        # BFS
        visited = {src}
        queue: deque[list[dict]] = deque()
        queue.append([{"entity": src, "rel_type": None, "direction": "start"}])

        while queue:
            path = queue.popleft()
            if len(path) > max_hops + 1:
                return None

            current = path[-1]["entity"]
            for neighbor, rel_type, direction in adj.get(current, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                new_path = path + [{"entity": neighbor, "rel_type": rel_type, "direction": direction}]
                if neighbor == tgt:
                    return new_path
                queue.append(new_path)

        return None

    def get_entity_counts_by_file(self) -> dict[str, int]:
        """Return entity count per source file: {source_path: count}."""
        rows = self._conn.execute(
            "SELECT source_path, COUNT(*) as c FROM kg_entities GROUP BY source_path"
        ).fetchall()
        return {r["source_path"]: r["c"] for r in rows}

    def get_entity_count_for_file(self, source_path: str) -> int:
        """Return entity count for a single file."""
        row = self._conn.execute(
            "SELECT COUNT(*) as c FROM kg_entities WHERE source_path = ?",
            (source_path,),
        ).fetchone()
        return row["c"]

    def get_entity_types(self) -> list[str]:
        """Return all distinct entity types."""
        rows = self._conn.execute(
            "SELECT DISTINCT entity_type FROM kg_entities ORDER BY entity_type"
        ).fetchall()
        return [r["entity_type"] for r in rows]

    def get_relationship_types(self) -> list[str]:
        """Return all distinct relationship types."""
        rows = self._conn.execute(
            "SELECT DISTINCT rel_type FROM kg_relationships ORDER BY rel_type"
        ).fetchall()
        return [r["rel_type"] for r in rows]

    def get_stats(self) -> dict:
        """Return KG statistics."""
        entities = self._conn.execute("SELECT COUNT(*) as c FROM kg_entities").fetchone()["c"]
        unique_entities = self._conn.execute(
            "SELECT COUNT(DISTINCT name || '::' || entity_type) as c FROM kg_entities"
        ).fetchone()["c"]
        relationships = self._conn.execute("SELECT COUNT(*) as c FROM kg_relationships").fetchone()["c"]
        sources = self._conn.execute(
            "SELECT COUNT(DISTINCT source_path) as c FROM kg_entities"
        ).fetchone()["c"]
        cached = self._conn.execute("SELECT COUNT(*) as c FROM kg_extraction_cache").fetchone()["c"]
        return {
            "entity_mentions": entities,
            "unique_entities": unique_entities,
            "relationships": relationships,
            "source_files": sources,
            "cached_chunks": cached,
        }
