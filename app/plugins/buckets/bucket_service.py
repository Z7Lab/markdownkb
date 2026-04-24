"""Business logic for temp buckets — ingestion, search, chat, cleanup."""

import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.embeddings.embedder import embed_texts
from app.ingestion.parser import parse_and_chunk, parse_markdown_content, chunk_text, Chunk
from app.rag.retriever import Retriever
from app.storage.vectorstore import VectorStore

from .bucketdb import BucketDB

logger = logging.getLogger(__name__)


def _stamp_indexed_at(metas: list[dict]) -> list[dict]:
    """Inject the current UTC timestamp into each chunk's metadata."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return [{**m, "indexed_at": ts} for m in metas]


class BucketService:
    """Manages bucket lifecycle: create, search, chat, delete, cleanup."""

    def __init__(self, bucketdb: BucketDB, chromadb_dir: str, embedding_model: str, remote_config: dict | None = None):
        self._db = bucketdb
        self._chromadb_dir = chromadb_dir
        self._embedding_model = embedding_model
        self._remote_config = remote_config
        self._store_cache: dict[str, VectorStore] = {}

    @property
    def db(self) -> BucketDB:
        return self._db

    def _collection_name(self, bucket_id: str) -> str:
        return f"bucket_{bucket_id}"

    def get_store(self, bucket_id: str) -> VectorStore:
        if bucket_id not in self._store_cache:
            self._store_cache[bucket_id] = VectorStore(
                persist_directory=self._chromadb_dir,
                collection_name=self._collection_name(bucket_id),
            )
        return self._store_cache[bucket_id]

    def get_retriever(self, bucket_id: str, settings) -> Retriever:
        store = self.get_store(bucket_id)
        return Retriever(store, settings)

    # -- Create --------------------------------------------------------------

    def create(
        self,
        name: str,
        sources: list[dict],
        expires_in: int | None = None,
        color: str | None = None,
        description: str | None = None,
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
            color=color,
            description=description,
        )
        bucket_id = record["id"]

        # Record which files belong to this bucket
        if scan_paths:
            self._db.set_file_memberships(bucket_id, scan_paths)

        # Embed and store in ChromaDB
        if all_docs:
            embeddings = embed_texts(all_docs, self._embedding_model, remote_config=self._remote_config)
            store = self.get_store(bucket_id)
            store.add(all_ids, all_docs, embeddings, _stamp_indexed_at(all_metas))
            logger.info(
                "Bucket '%s' created: %d files, %d chunks",
                name, file_count, len(all_ids),
            )
        else:
            logger.info("Bucket '%s' created with no documents", name)

        return record

    # -- Add documents -------------------------------------------------------

    def add_documents(self, bucket: str, sources: list[dict]) -> dict:
        """Add documents to an existing bucket.

        Parses, chunks, and embeds new files into the bucket's existing
        ChromaDB collection.  Skips files already present (by source_path).
        """
        record = self._db.resolve(bucket)
        if not record:
            raise ValueError(f"Bucket not found: {bucket}")

        bucket_id = record["id"]
        bucket_name = record["name"]

        # Discover existing file paths so we can skip duplicates
        store = self.get_store(bucket_id)
        existing_paths: set[str] = set()
        for meta in store.get_all_metadatas():
            path = meta.get("source_path", "")
            if path:
                existing_paths.add(path)

        # Resolve source paths for scanning
        scan_paths: list[str] = []
        for src in sources:
            path = src.get("path", "")
            glob_pattern = src.get("glob", "**/*.md")
            resolved = Path(path).resolve()
            if resolved.is_file():
                scan_paths.append(str(resolved))
            elif resolved.is_dir():
                for match in resolved.glob(glob_pattern):
                    if match.is_file() and match.suffix == ".md":
                        scan_paths.append(str(match))

        # Parse, chunk, and embed new files only
        all_ids: list[str] = []
        all_docs: list[str] = []
        all_metas: list[dict] = []
        added_files = 0
        skipped_files = 0
        new_file_paths: list[str] = []

        for file_path in scan_paths:
            if file_path in existing_paths:
                skipped_files += 1
                continue
            if not Path(file_path).exists():
                logger.warning("Bucket add: file not found: %s", file_path)
                continue
            source_root = str(Path(file_path).parent)
            chunks = parse_and_chunk(file_path, source_root)
            if not chunks:
                continue
            added_files += 1
            new_file_paths.append(file_path)
            for i, chunk in enumerate(chunks):
                chunk_id = f"bucket:{bucket_name}:{file_path}:{i}"
                all_ids.append(chunk_id)
                all_docs.append(chunk.content)
                all_metas.append(chunk.metadata)

        if all_docs:
            embeddings = embed_texts(all_docs, self._embedding_model, remote_config=self._remote_config)
            store.add(all_ids, all_docs, embeddings, _stamp_indexed_at(all_metas))

        # Update membership records for newly added files
        if new_file_paths:
            self._db.set_file_memberships(bucket_id, new_file_paths)

        # Update metadata counts
        new_file_count = record["file_count"] + added_files
        new_chunk_count = record["chunk_count"] + len(all_ids)
        self._db.update_counts(bucket_id, new_file_count, new_chunk_count)

        logger.info(
            "Bucket '%s': added %d files (%d chunks), skipped %d existing",
            bucket_name, added_files, len(all_ids), skipped_files,
        )

        return {
            "bucket_id": bucket_id,
            "bucket_name": bucket_name,
            "added_files": added_files,
            "added_chunks": len(all_ids),
            "skipped_files": skipped_files,
            "total_files": new_file_count,
            "total_chunks": new_chunk_count,
        }

    # -- Push (inline content, no filesystem) ---------------------------------

    def push_documents(
        self,
        bucket: str,
        documents: list[dict],
    ) -> dict:
        """Push markdown documents into a bucket by content (no filesystem access needed).

        Each document dict must have ``name`` (virtual filename ending in .md)
        and ``content`` (raw markdown text).  Documents with identical content
        (by SHA-256 hash) are skipped as duplicates. Filename collisions are
        resolved by appending a counter suffix.
        """
        record = self._db.resolve(bucket)
        if not record:
            raise ValueError(f"Bucket not found: {bucket}")

        bucket_id = record["id"]
        bucket_name = record["name"]

        store = self.get_store(bucket_id)
        existing_paths: set[str] = set()
        existing_hashes: set[str] = set()
        for meta in store.get_all_metadatas():
            path = meta.get("source_path", "")
            if path:
                existing_paths.add(path)
            h = meta.get("content_hash", "")
            if h:
                existing_hashes.add(h)

        all_ids: list[str] = []
        all_docs: list[str] = []
        all_metas: list[dict] = []
        added_files = 0
        skipped_files = 0

        for doc in documents:
            name = doc.get("name", "")
            content = doc.get("content", "")
            if not name or not content:
                continue
            if not name.endswith(".md"):
                name = f"{name}.md"

            content_hash = hashlib.sha256(content.encode()).hexdigest()
            if content_hash in existing_hashes:
                skipped_files += 1
                continue

            # Resolve filename collisions by appending a counter
            stem = name[:-3]
            candidate = name
            counter = 1
            while f"bucket://{bucket_name}/{candidate}" in existing_paths:
                candidate = f"{stem}-{counter}.md"
                counter += 1
            name = candidate
            virtual_path = f"bucket://{bucket_name}/{name}"

            raw_chunks = parse_markdown_content(content, virtual_path, source_root=f"bucket://{bucket_name}")
            sized_chunks: list[Chunk] = []
            global_idx = 0
            for chunk in raw_chunks:
                sub_texts = chunk_text(chunk.content, 1500, 150)
                for sub in sub_texts:
                    meta = dict(chunk.metadata)
                    meta["chunk_index"] = global_idx
                    sized_chunks.append(Chunk(content=sub, metadata=meta))
                    global_idx += 1

            if not sized_chunks:
                continue

            added_files += 1
            existing_hashes.add(content_hash)
            existing_paths.add(virtual_path)
            for i, chunk in enumerate(sized_chunks):
                chunk_id = f"bucket:{bucket_name}:{virtual_path}:{i}"
                all_ids.append(chunk_id)
                all_docs.append(chunk.content)
                m = dict(chunk.metadata)
                m["content_hash"] = content_hash
                all_metas.append(m)

        if all_docs:
            embeddings = embed_texts(all_docs, self._embedding_model, remote_config=self._remote_config)
            store.add(all_ids, all_docs, embeddings, _stamp_indexed_at(all_metas))

        new_file_count = record["file_count"] + added_files
        new_chunk_count = record["chunk_count"] + len(all_ids)
        self._db.update_counts(bucket_id, new_file_count, new_chunk_count)

        logger.info(
            "Bucket '%s': pushed %d documents (%d chunks), skipped %d existing",
            bucket_name, added_files, len(all_ids), skipped_files,
        )

        return {
            "bucket_id": bucket_id,
            "bucket_name": bucket_name,
            "added_files": added_files,
            "added_chunks": len(all_ids),
            "skipped_files": skipped_files,
            "total_files": new_file_count,
            "total_chunks": new_chunk_count,
        }

    # -- Search --------------------------------------------------------------

    def search(self, bucket: str, query: str, top_k: int, settings) -> dict:
        """Search within a bucket. Returns retrieve-compatible format."""
        record = self._db.resolve(bucket)
        if not record:
            raise ValueError(f"Bucket not found: {bucket}")

        retriever = self.get_retriever(record["id"], settings)
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

        retriever = self.get_retriever(record["id"], settings)

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
        collection_deleted = True
        try:
            store = self.get_store(bucket_id)
            store.clear()
        except Exception as e:
            logger.warning("Failed to delete ChromaDB collection for bucket %s: %s", bucket_id, e)
            collection_deleted = False

        self._db.delete(bucket_id)
        self._store_cache.pop(bucket_id, None)
        logger.info("Bucket '%s' (%s) deleted", bucket_name, bucket_id)
        result = {"deleted": True, "id": bucket_id, "name": bucket_name}
        if not collection_deleted:
            result["partial"] = True
            result["warning"] = "Bucket record deleted but ChromaDB collection cleanup failed"
        return result

    # -- Flag expired (does NOT delete) --------------------------------------

    def flag_expired(self) -> int:
        """Flag expired buckets as expired in place. Does NOT delete them.

        Expired buckets remain visible in the UI until explicitly deleted.
        Returns count of newly flagged buckets.
        """
        newly_expired = self._db.get_expired()
        flagged = 0
        for record in newly_expired:
            self._db.mark_expired(record["id"])
            flagged += 1
            logger.info("Bucket '%s' (%s) flagged as expired", record["name"], record["id"])
        return flagged
