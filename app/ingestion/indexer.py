"""Shared indexing logic for CLI, API, and main app."""

import logging
from typing import Callable

from app.config import Settings
from app.embeddings.embedder import embed_texts
from app.ingestion.parser import parse_and_chunk
from app.ingestion.scanner import scan_sources, FileInfo
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def _classify_files(files, tracking, incomplete):
    """Split files into (to_index, skipped_count) based on hash comparison."""
    hash_map = tracking.get_hash_map()
    to_index = []
    skipped = 0

    for fi in files:
        stored_hash = hash_map.get(fi.path)
        if stored_hash is None or fi.content_hash != stored_hash:
            to_index.append(fi)
        elif fi.path in incomplete:
            to_index.append(fi)
        else:
            skipped += 1

    return to_index, skipped


def _index_file(fi: FileInfo, settings: Settings,
                store: VectorStore, tracking: TrackingDB) -> int:
    """Index a single file. Returns chunk count, raises on failure."""
    tracking.upsert_file(
        fi.path, fi.source_root, fi.content_hash,
        fi.size, fi.modified, status="indexing",
    )
    store.delete_by_source(fi.path)

    chunks = parse_and_chunk(
        fi.path, fi.source_root,
        settings.chunk_size, settings.chunk_overlap,
    )
    if not chunks:
        tracking.mark_complete(fi.path, 0)
        return 0

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]
        texts = [c.content for c in batch]
        embeddings = embed_texts(texts)
        ids = [c.chunk_id for c in batch]
        metadatas = [c.metadata for c in batch]
        store.add(ids, texts, embeddings, metadatas)

    tracking.mark_complete(fi.path, len(chunks))
    return len(chunks)


def run_index(
    settings: Settings,
    store: VectorStore,
    tracking: TrackingDB,
    progress: Callable[[float, str], None] | None = None,
) -> str:
    """Smart index: skip unchanged, reindex changed, clean deleted.

    Uses the tracking DB to compare file hashes and only embed files
    that are new or changed. Saves per-file so partial progress
    survives crashes.
    """
    def report(frac: float, msg: str):
        logger.info(msg)
        if progress:
            progress(frac, msg)

    report(0.0, "Scanning source directories...")
    files = scan_sources(settings.sources, settings.global_ignore)
    scanned_paths = {fi.path for fi in files}

    incomplete = set(tracking.recover_incomplete())
    if incomplete:
        report(0.02, f"Recovering {len(incomplete)} interrupted files...")

    removed = tracking.remove_files_not_in(scanned_paths)
    for path in removed:
        store.delete_by_source(path)
    if removed:
        report(0.05, f"Removed {len(removed)} deleted files")

    to_index, skipped = _classify_files(files, tracking, incomplete)

    if not to_index and not removed:
        msg = f"All {len(files)} files up to date. Store total: {store.count}"
        report(1.0, msg)
        return msg

    report(0.1, f"{len(to_index)} files to index ({skipped} unchanged)...")

    total_chunks = 0
    errors = 0
    for i, fi in enumerate(to_index):
        frac = 0.1 + 0.85 * (i / max(len(to_index), 1))
        report(frac, f"Indexing {fi.relative_path}...")

        try:
            total_chunks += _index_file(fi, settings, store, tracking)
        except (OSError, ValueError, RuntimeError) as exc:
            tracking.mark_error(fi.path, str(exc))
            logger.error("Failed to index %s: %s", fi.path, exc)
            errors += 1

    parts = [
        f"Indexed {len(to_index)} files ({total_chunks} chunks)",
        f"{skipped} unchanged",
    ]
    if removed:
        parts.append(f"{len(removed)} deleted")
    if errors:
        parts.append(f"{errors} errors")
    parts.append(f"Store total: {store.count}")

    msg = ", ".join(parts)
    report(1.0, msg)
    return msg
