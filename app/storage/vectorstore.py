"""ChromaDB vector store for persistent chunk storage and retrieval."""

import logging
from pathlib import Path
from typing import Any

import chromadb

logger = logging.getLogger(__name__)


class VectorStore:
    """Persistent vector store backed by ChromaDB for chunk storage and search."""

    def __init__(self, persist_directory: str = "./data/chromadb",
                 collection_name: str = "mdkb"):
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_directory)
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

    def delete_by_source(self, source_path: str):
        """Delete all chunks from a given source file."""
        try:
            self._collection.delete(where={"source_path": source_path})
        except ValueError as e:
            logger.warning("Failed to delete chunks for %s: %s", source_path, e)

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
            flat[k] = ""
        else:
            flat[k] = str(v)
    return flat
