"""Shared indexing logic for CLI, API, and main app."""

import logging
import threading
import time
from pathlib import Path
from typing import Callable

from app.config import Settings
from app.embeddings.embedder import embed_texts
from app.events import IndexEvent, event_bus
from app.ingestion.parser import parse_and_chunk
from app.ingestion.scanner import scan_sources, compute_file_hash, FileInfo
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def _classify_files(files, tracking, incomplete):
    """Split files into (to_index, skipped_count) based on hash comparison."""
    hash_map = tracking.get_hash_map()
    excluded = tracking.get_rag_excluded_paths()
    to_index = []
    skipped = 0

    for fi in files:
        if fi.path in excluded:
            skipped += 1
            continue
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

    # Capture model ID once per file to avoid mid-file model switches
    embedding_model = settings.embedding_model
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]
        texts = [c.content for c in batch]
        embeddings = embed_texts(texts, embedding_model)
        ids = [c.chunk_id for c in batch]
        metadatas = [c.metadata for c in batch]
        store.add(ids, texts, embeddings, metadatas)

    # Extract file-level tags from first chunk's frontmatter metadata
    file_tags = ""
    if chunks:
        raw_tags = chunks[0].metadata.get("tags", "")
        if isinstance(raw_tags, list):
            file_tags = ", ".join(str(t) for t in raw_tags)
        elif isinstance(raw_tags, str):
            file_tags = raw_tags

    tracking.mark_complete(fi.path, len(chunks))
    if file_tags:
        from app.tag_utils import notify_tags_extracted
        notify_tags_extracted(fi.path, file_tags)
    return len(chunks)


def run_index(
    settings: Settings,
    store: VectorStore,
    tracking: TrackingDB,
    progress: Callable[[float, str], None] | None = None,
    cancel: threading.Event | None = None,
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

    logger.info("run_index starting with embedding_model=%s", settings.embedding_model)
    report(0.0, "Scanning source directories...")
    files = scan_sources(settings.sources, settings.global_ignore)

    incomplete = set(tracking.recover_incomplete())
    if incomplete:
        report(0.02, f"Recovering {len(incomplete)} interrupted files...")

    removed = tracking.remove_files_not_in(
        {fi.path for fi in files}
    )
    for path in removed:
        store.delete_by_source(path)
        event_bus.publish(IndexEvent(
            type="deleted", path=path, filename=Path(path).name,
        ))
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
    done = 0
    for fi in to_index:
        if cancel and cancel.is_set():
            report(0.95, "Cancelled by user")
            break

        frac = 0.1 + 0.85 * (done / max(len(to_index), 1))
        report(frac, f"Indexing {fi.relative_path}...")
        event_bus.publish(IndexEvent(
            type="indexing", path=fi.path, filename=fi.relative_path,
        ))

        try:
            chunk_count = _index_file(fi, settings, store, tracking)
            total_chunks += chunk_count
            event_bus.publish(IndexEvent(
                type="indexed", path=fi.path,
                filename=fi.relative_path, chunks=chunk_count,
            ))
        except (OSError, ValueError, RuntimeError) as exc:
            tracking.mark_error(fi.path, str(exc))
            logger.error("Failed to index %s: %s", fi.path, exc)
            errors += 1
            event_bus.publish(IndexEvent(
                type="error", path=fi.path,
                filename=fi.relative_path, error=str(exc),
            ))
        done += 1

        # Yield CPU between files to avoid pegging 100%
        time.sleep(0.02)

    parts = [
        f"Indexed {done}/{len(to_index)} files ({total_chunks} chunks)",
        f"{skipped} unchanged",
    ]
    if cancel and cancel.is_set():
        parts.insert(0, "Cancelled")
    if removed:
        parts.append(f"{len(removed)} deleted")
    if errors:
        parts.append(f"{errors} errors")
    parts.append(f"Store total: {store.count}")

    msg = ", ".join(parts)
    report(1.0, msg)
    return msg


class ReindexError(Exception):
    """Raised when reindex_file encounters a recoverable error."""


def reindex_file(
    path: str, settings: Settings,
    store: VectorStore, tracking: TrackingDB,
) -> str:
    """Re-index a single file and return a status message.

    Raises:
        ReindexError: If the file is not found or not in a watch directory.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise ReindexError(f"File not found: {p.name}")

    record = tracking.get_file(str(p))
    if record:
        source_root = record["source_root"]
    else:
        # Discover source_root from settings for untracked files
        source_root = ""
        for src in settings.sources:
            src_resolved = str(Path(src).resolve())
            if str(p).startswith(src_resolved + "/"):
                source_root = src_resolved
                break
        if not source_root:
            raise ReindexError(f"File not in any watch directory: {p.name}")

    stat = p.stat()
    fi = FileInfo(
        path=str(p),
        relative_path=p.name,
        size=stat.st_size,
        modified=stat.st_mtime,
        content_hash=compute_file_hash(str(p)),
        source_root=source_root,
    )
    try:
        chunks = _index_file(fi, settings, store, tracking)
        return f"Indexed: {p.name} ({chunks} chunks)"
    except (OSError, ValueError, RuntimeError) as exc:
        tracking.mark_error(str(p), str(exc))
        raise ReindexError(f"Error indexing {p.name}: {exc}") from exc


def index_directory(
    path: str,
    settings: Settings,
    store: VectorStore,
    tracking: TrackingDB,
) -> str:
    """Index only files in a single directory (not all sources)."""
    files = scan_sources([path], settings.global_ignore)
    to_index, skipped = _classify_files(files, tracking, set())

    if not to_index:
        return f"All {len(files)} files in {path} up to date"

    total_chunks = 0
    errors = 0
    for fi in to_index:
        try:
            total_chunks += _index_file(fi, settings, store, tracking)
            event_bus.publish(IndexEvent(
                type="indexed", path=fi.path,
                filename=fi.relative_path, chunks=total_chunks,
            ))
        except (OSError, ValueError, RuntimeError) as exc:
            tracking.mark_error(fi.path, str(exc))
            logger.error("Failed to index %s: %s", fi.path, exc)
            errors += 1
        time.sleep(0.02)

    return f"Indexed {len(to_index)} files ({total_chunks} chunks, {errors} errors) in {path}"
