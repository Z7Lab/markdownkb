"""Shared indexing logic for CLI, API, and main app."""

import logging
from typing import Callable

from app.config import Settings
from app.embeddings.embedder import embed_texts
from app.ingestion.parser import parse_and_chunk
from app.ingestion.scanner import scan_sources
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def run_index(
    settings: Settings,
    store: VectorStore,
    progress: Callable[[float, str], None] | None = None,
) -> str:
    """Scan sources, parse, embed, and store all markdown chunks.

    Skips chunks that are already in the store (by ID). Processes new
    chunks in batches and saves incrementally so partial progress
    survives crashes. The optional progress callback receives (fraction, message).
    """
    def report(frac: float, msg: str):
        logger.info(msg)
        if progress:
            progress(frac, msg)

    report(0.0, "Scanning source directories...")
    files = scan_sources(settings.sources, settings.global_ignore)
    report(0.05, f"Found {len(files)} markdown files, parsing...")

    all_chunks = []
    for fi in files:
        chunks = parse_and_chunk(
            fi.path, fi.source_root,
            settings.chunk_size, settings.chunk_overlap,
        )
        all_chunks.extend(chunks)

    if not all_chunks:
        return "No markdown files found to index."

    # Filter out chunks already in the store
    existing_ids = store.get_existing_ids()
    new_chunks = [c for c in all_chunks if c.chunk_id not in existing_ids]
    skipped = len(all_chunks) - len(new_chunks)

    if not new_chunks:
        msg = (
            f"All {len(all_chunks)} chunks already indexed. "
            f"Store total: {store.count}"
        )
        report(1.0, msg)
        return msg

    report(
        0.1,
        f"{len(new_chunks)} new chunks to embed "
        f"({skipped} already indexed)...",
    )

    stored = 0
    total = len(new_chunks)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch = new_chunks[start:end]

        texts = [c.content for c in batch]
        embeddings = embed_texts(texts)
        ids = [c.chunk_id for c in batch]
        metadatas = [c.metadata for c in batch]

        store.add(ids, texts, embeddings, metadatas)
        stored += len(batch)

        frac = 0.1 + 0.9 * (stored / total)
        report(frac, f"Embedded {stored}/{total} new chunks...")

    msg = (
        f"Indexed {len(files)} files: {stored} new, "
        f"{skipped} unchanged. Store total: {store.count}"
    )
    report(1.0, msg)
    return msg
