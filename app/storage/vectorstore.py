"""ChromaDB vector store for persistent chunk storage and retrieval."""

import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)


class VectorStore:
    """Persistent vector store backed by ChromaDB for chunk storage and search."""

    def __init__(self, persist_directory: str,
                 collection_name: str = "markdownkb"):
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "VectorStore initialized: %s, collection=%s, count=%d",
            persist_directory, collection_name, self._collection.count(),
        )

    @property
    def count(self) -> int:
        """Return the number of chunks in the collection."""
        return self._collection.count()

    def get_stored_dimensions(self) -> int | None:
        """Return the vector dimension of stored embeddings, or None if collection is empty."""
        if self._collection.count() == 0:
            return None
        result = self._collection.get(include=["embeddings"], limit=1)
        embs = result.get("embeddings")
        if embs is not None and len(embs) > 0 and embs[0] is not None and len(embs[0]) > 0:
            return len(embs[0])
        return None

    def add(self, ids: list[str], documents: list[str],
            embeddings: list[list[float]], metadatas: list[dict] | None = None):
        """Add or update chunks in the vector store."""
        # ChromaDB metadata values must be str, int, float, or bool
        clean_metadatas = None
        if metadatas:
            clean_metadatas = [_flatten_metadata(m) for m in metadatas]

        batch_size = 500
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            self._collection.upsert(
                ids=ids[i:end],
                documents=documents[i:end],
                embeddings=embeddings[i:end],
                metadatas=clean_metadatas[i:end] if clean_metadatas else None,
            )

    def query(self, query_embedding: list[float], n_results: int = 5,
              where: dict | None = None) -> dict:
        """Query the vector store and return matching documents with scores."""
        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, max(self._collection.count(), 1)),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)
        return {
            "ids": results["ids"][0] if results["ids"] else [],
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
        }

    def get_all_metadatas(self) -> list[dict]:
        """Return metadata for all stored chunks."""
        if self._collection.count() == 0:
            return []
        result = self._collection.get(include=["metadatas"])
        return result["metadatas"] or []

    def get_all_with_embeddings(
        self, source_roots: list[str] | None = None,
    ) -> dict:
        """Return all chunks with documents, embeddings, and metadatas.

        Args:
            source_roots: Optional list of source_root values to filter by.

        Returns dict with keys: ids, documents, embeddings, metadatas.
        """
        if self._collection.count() == 0:
            return {"ids": [], "documents": [], "embeddings": [], "metadatas": []}

        kwargs: dict[str, Any] = {
            "include": ["documents", "embeddings", "metadatas"],
        }
        if source_roots:
            if len(source_roots) == 1:
                kwargs["where"] = {"source_root": source_roots[0]}
            else:
                kwargs["where"] = {"source_root": {"$in": source_roots}}

        return self._collection.get(**kwargs)

    def get_chunks_for_doc(self, source_path: str) -> dict:
        """Return chunks with documents and embeddings for a single source file."""
        if self._collection.count() == 0:
            return {"ids": [], "documents": [], "embeddings": []}
        result = self._collection.get(
            where={"source_path": source_path},
            include=["documents", "embeddings"],
        )
        return result

    def delete_by_source(self, source_path: str):
        """Delete all chunks from a given source file.

        ChromaDB raises ValueError when no documents match the filter
        (e.g., first-time indexing).  This is benign and safe to ignore.
        """
        try:
            self._collection.delete(where={"source_path": source_path})
        except ValueError as e:
            # ChromaDB raises ValueError for empty filter results.
            # Log at debug for expected "no docs" case, warn for anything else.
            logger.debug(
                "ValueError deleting chunks for %s (likely no matching docs): %s",
                source_path, e,
            )

    def rename_source(self, old_path: str, new_path: str,
                      new_source_root: str) -> int:
        """Update source_path for all chunks of a file, preserving embeddings.

        Returns the number of chunks moved, or 0 if no chunks found.
        """
        try:
            result = self._collection.get(
                where={"source_path": old_path},
                include=["embeddings", "documents", "metadatas"],
            )
        except ValueError:
            return 0

        if not result["ids"]:
            return 0

        # Delete old chunks
        self._collection.delete(where={"source_path": old_path})

        # Build new IDs and metadata with updated paths
        new_ids = [
            old_id.replace(old_path, new_path, 1)
            for old_id in result["ids"]
        ]
        new_metadatas = []
        for meta in result["metadatas"]:
            updated = dict(meta)
            updated["source_path"] = new_path
            updated["source_root"] = new_source_root
            new_metadatas.append(updated)

        # Re-insert with preserved embeddings and documents
        self.add(new_ids, result["documents"], result["embeddings"],
                 new_metadatas)

        logger.info("Renamed source %s → %s (%d chunks)",
                     old_path, new_path, len(new_ids))
        return len(new_ids)

    def clear(self):
        """Delete all chunks and recreate the collection."""
        self._client.delete_collection(self._collection.name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection.name,
            metadata={"hnsw:space": "cosine"},
        )


def _flatten_metadata(meta: dict) -> dict:
    """Flatten metadata values to types supported by ChromaDB."""
    flat: dict[str, str | int | float | bool] = {}
    for k, v in meta.items():
        if isinstance(v, (str, int, float, bool)):
            flat[k] = v
        elif isinstance(v, dict):
            flat[k] = str(v)
        elif isinstance(v, list):
            flat[k] = ", ".join(str(x) for x in v)
        elif v is None:
            # Skip None values rather than storing as empty string,
            # which would be indistinguishable from intentional empty strings
            continue
        else:
            flat[k] = str(v)
    return flat
