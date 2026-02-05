"""File system watcher for automatic re-indexing on changes."""

import fnmatch
import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from app.config import Settings
from app.embeddings.embedder import embed_texts
from app.ingestion.parser import parse_and_chunk
from app.ingestion.scanner import compute_file_hash
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)


def reindex_file(
    filepath: str, settings: Settings,
    store: VectorStore, tracking: TrackingDB,
):
    """Re-index a single markdown file, updating the vector store."""
    filepath = str(Path(filepath).resolve())

    if not filepath.endswith(".md"):
        return

    if not Path(filepath).exists():
        logger.info("File deleted, removing from index: %s", filepath)
        store.delete_by_source(filepath)
        tracking.remove_file(filepath)
        return

    current_hash = compute_file_hash(filepath)
    stored_hash = tracking.get_hash(filepath)
    if current_hash == stored_hash:
        logger.debug("File unchanged, skipping: %s", filepath)
        return

    logger.info("Re-indexing: %s", filepath)
    tracking.mark_indexing(filepath)

    # Remove old chunks
    store.delete_by_source(filepath)

    # Find which source root this file belongs to
    source_root = ""
    for src in settings.sources:
        resolved = str(Path(src).resolve())
        if filepath.startswith(resolved):
            source_root = resolved
            break

    try:
        chunks = parse_and_chunk(
            filepath, source_root,
            settings.chunk_size, settings.chunk_overlap,
        )

        if not chunks:
            tracking.remove_file(filepath)
            return

        texts = [c.content for c in chunks]
        embeddings = embed_texts(texts)
        ids = [c.chunk_id for c in chunks]
        metadatas = [c.metadata for c in chunks]

        store.add(ids, texts, embeddings, metadatas)

        stat = Path(filepath).stat()
        tracking.upsert_file(
            filepath, source_root, current_hash,
            stat.st_size, stat.st_mtime,
            status="complete", chunk_count=len(chunks),
        )
        logger.info("Re-indexed %s: %d chunks", filepath, len(chunks))

    except (OSError, ValueError, RuntimeError) as exc:
        tracking.mark_error(filepath, str(exc))
        logger.error("Failed to re-index %s: %s", filepath, exc)


class MarkdownHandler(FileSystemEventHandler):
    """Watchdog event handler that triggers re-indexing for markdown files."""

    def __init__(
        self, settings: Settings, store: VectorStore,
        tracking: TrackingDB,
    ):
        self._settings = settings
        self._store = store
        self._tracking = tracking
        self._debounce: dict[str, float] = {}

    def _should_process(self, path: str) -> bool:
        """Check if a file event should trigger re-indexing."""
        if not path.endswith(".md"):
            return False
        for pattern in self._settings.global_ignore:
            if fnmatch.fnmatch(path, pattern):
                return False
        now = time.time()
        last = self._debounce.get(path, 0)
        if now - last < 2.0:
            return False
        self._debounce[path] = now
        return True

    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            reindex_file(
                event.src_path, self._settings,
                self._store, self._tracking,
            )

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            reindex_file(
                event.src_path, self._settings,
                self._store, self._tracking,
            )

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events."""
        if event.is_directory:
            return
        if event.src_path.endswith(".md"):
            resolved = str(Path(event.src_path).resolve())
            logger.info("File deleted: %s", resolved)
            self._store.delete_by_source(resolved)
            self._tracking.remove_file(resolved)


def start_watching(
    settings: Settings, store: VectorStore,
    tracking: TrackingDB,
):
    """Start the file system observer for all configured sources."""
    handler = MarkdownHandler(settings, store, tracking)
    observer = Observer()

    for source in settings.sources:
        source_path = Path(source).resolve()
        if source_path.exists() and source_path.is_dir():
            observer.schedule(
                handler, str(source_path), recursive=True,
            )
            logger.info("Watching: %s", source_path)

    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
