"""Shared indexing logic for CLI, API, and main app."""

import logging

from app.config import Settings
from app.embeddings.embedder import embed_texts
from app.ingestion.parser import parse_and_chunk
from app.ingestion.scanner import scan_sources
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)


def run_index(settings: Settings, store: VectorStore) -> str:
    """Scan sources, parse, embed, and store all markdown chunks."""
    logger.info("Starting indexing...")
    files = scan_sources(settings.sources, settings.global_ignore)
    logger.info("Found %d markdown files", len(files))

    all_chunks = []
    for fi in files:
        chunks = parse_and_chunk(
            fi.path, fi.source_root,
            settings.chunk_size, settings.chunk_overlap,
        )
        all_chunks.extend(chunks)

    if not all_chunks:
        return "No markdown files found to index."

    logger.info("Embedding %d chunks...", len(all_chunks))
    texts = [c.content for c in all_chunks]
    embeddings = embed_texts(texts)

    ids = [c.chunk_id for c in all_chunks]
    metadatas = [c.metadata for c in all_chunks]

    store.add(ids, texts, embeddings, metadatas)
    msg = (
        f"Indexed {len(files)} files, {len(all_chunks)} chunks. "
        f"Store total: {store.count}"
    )
    logger.info(msg)
    return msg
