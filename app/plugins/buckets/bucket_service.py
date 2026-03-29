"""Business logic for temp buckets — ingestion, search, chat, cleanup."""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.embeddings.embedder import embed_texts
from app.ingestion.parser import parse_and_chunk
from app.ingestion.scanner import scan_sources
from app.rag.retriever import Retriever, SearchResult
from app.storage.vectorstore import VectorStore

from .bucketdb import BucketDB

logger = logging.getLogger(__name__)


class BucketService:
    """Manages bucket lifecycle: create, search, chat, delete, cleanup."""

    def __init__(self, bucketdb: BucketDB, chromadb_dir: str, embedding_model: str):
        self._db = bucketdb
        self._chromadb_dir = chromadb_dir
        self._embedding_model = embedding_model

    @property
    def db(self) -> BucketDB:
        return self._db

    def _collection_name(self, bucket_id: str) -> str:
        return f"bucket_{bucket_id}"

    def _get_store(self, bucket_id: str) -> VectorStore:
        return VectorStore(
            persist_directory=self._chromadb_dir,
            collection_name=self._collection_name(bucket_id),
        )

    def _get_retriever(self, bucket_id: str, settings) -> Retriever:
        store = self._get_store(bucket_id)
        return Retriever(store, settings)

    # -- Create --------------------------------------------------------------

    def create(
        self,
        name: str,
        sources: list[dict],
        expires_in: int | None = None,
    ) -> dict:
        """Create a bucket, ingest sources, return metadata."""
        if self._db.name_exists(name):
            raise ValueError(f"Bucket name already exists: {name}")

        # Resolve source paths for scanning
        scan_paths: list[str] = []
        for src in sources:
            path = src.get("path", "")
            glob_pattern = src.get("glob", "**/*.md")
            resolved = Path(path).resolve()
            if resolved.is_file():
                scan_paths.append(str(resolved))
            elif resolved.is_dir():
                # Collect matching files
                for match in resolved.glob(glob_pattern):
                    if match.is_file() and match.suffix == ".md":
                        scan_paths.append(str(match))

        # Parse and chunk all files
        all_ids: list[str] = []
        all_docs: list[str] = []
        all_metas: list[dict] = []
        file_count = 0

        for file_path in scan_paths:
            if not Path(file_path).exists():
                logger.warning("Bucket source file not found: %s", file_path)
                continue
            source_root = str(Path(file_path).parent)
            chunks = parse_and_chunk(file_path, source_root)
            if not chunks:
                continue
            file_count += 1
            for i, chunk in enumerate(chunks):
                chunk_id = f"bucket:{name}:{file_path}:{i}"
                all_ids.append(chunk_id)
                all_docs.append(chunk.content)
                all_metas.append(chunk.metadata)

        # Embed and store
        expires_at = None
        if expires_in and expires_in > 0:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            ).strftime("%Y-%m-%d %H:%M:%S")

        # Create DB record first to get the ID
        record = self._db.create(
            name=name,
            sources=json.dumps(sources),
            file_count=file_count,
            chunk_count=len(all_ids),
            expires_at=expires_at,
        )
        bucket_id = record["id"]

        # Embed and store in ChromaDB
        if all_docs:
            embeddings = embed_texts(all_docs, self._embedding_model)
            store = self._get_store(bucket_id)
            store.add(all_ids, all_docs, embeddings, all_metas)
            logger.info(
                "Bucket '%s' created: %d files, %d chunks",
                name, file_count, len(all_ids),
            )
        else:
            logger.info("Bucket '%s' created with no documents", name)

        return record

    # -- Search --------------------------------------------------------------

    def search(self, bucket: str, query: str, top_k: int, settings) -> dict:
        """Search within a bucket. Returns retrieve-compatible format."""
        record = self._db.resolve(bucket)
        if not record:
            raise ValueError(f"Bucket not found: {bucket}")

        retriever = self._get_retriever(record["id"], settings)
        results = retriever.search(query, top_k=top_k)

        formatted = [
            {
                "content": r.document,
                "source": r.metadata.get("source_path", ""),
                "score": round(r.score, 4),
            }
            for r in results
        ]
        return {"results": formatted, "total": len(results)}

    # -- Chat ----------------------------------------------------------------

    def chat(self, bucket: str, message: str, settings) -> dict:
        """RAG chat scoped to a bucket."""
        from app.services.chat_service import chat_respond

        record = self._db.resolve(bucket)
        if not record:
            raise ValueError(f"Bucket not found: {bucket}")

        retriever = self._get_retriever(record["id"], settings)

        sources: list[str] = []
        source_map: dict[str, str] = {}
        response = ""
        for chunk in chat_respond(
            message, retriever, settings,
            sources_out=sources, source_map_out=source_map,
        ):
            response = chunk

        return {"response": response, "sources": sources, "source_map": source_map}

    # -- Delete --------------------------------------------------------------

    def delete(self, bucket: str) -> dict:
        """Delete a bucket and its ChromaDB collection."""
        record = self._db.resolve(bucket)
        if not record:
            raise ValueError(f"Bucket not found: {bucket}")

        bucket_id = record["id"]
        bucket_name = record["name"]

        # Delete ChromaDB collection
        try:
            store = self._get_store(bucket_id)
            store.clear()
        except Exception:
            logger.warning("Failed to delete ChromaDB collection for bucket %s", bucket_id)

        self._db.delete(bucket_id)
        logger.info("Bucket '%s' (%s) deleted", bucket_name, bucket_id)
        return {"deleted": True, "id": bucket_id, "name": bucket_name}

    # -- Cleanup expired -----------------------------------------------------

    def cleanup_expired(self) -> int:
        """Delete expired buckets. Returns count of cleaned up buckets."""
        expired = self._db.get_expired()
        for record in expired:
            try:
                self.delete(record["id"])
            except Exception:
                logger.warning("Failed to clean up expired bucket %s", record["id"])
        if expired:
            logger.info("Cleaned up %d expired bucket(s)", len(expired))
        return len(expired)
