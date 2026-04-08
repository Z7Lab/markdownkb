"""File system watcher for automatic re-indexing on changes."""

import fnmatch
import logging
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from app.config import Settings
from app.embeddings.embedder import embed_texts
from app.events import IndexEvent, event_bus
from app.ingestion.parser import parse_and_chunk
from app.ingestion.scanner import compute_file_hash
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)


def _filename(path: str) -> str:
    return Path(path).name


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
        from app.tag_utils import notify_file_deleted
        notify_file_deleted(filepath)
        event_bus.publish(IndexEvent(
            type="deleted", path=filepath, filename=_filename(filepath),
        ))
        return

    if filepath in tracking.get_rag_excluded_paths():
        logger.debug("File excluded from RAG, skipping: %s", filepath)
        return

    current_hash = compute_file_hash(filepath)
    stored_hash = tracking.get_hash(filepath)
    if current_hash == stored_hash:
        logger.debug("File unchanged, skipping: %s", filepath)
        return

    logger.info("Re-indexing: %s", filepath)
    tracking.mark_indexing(filepath)
    event_bus.publish(IndexEvent(
        type="indexing", path=filepath, filename=_filename(filepath),
    ))

    # Remove old chunks
    store.delete_by_source(filepath)

    # Find which source root this file belongs to
    source_root = ""
    for src in settings.sources:
        resolved = str(Path(src).resolve())
        if filepath.startswith(resolved + "/"):
            source_root = resolved
            break

    if not source_root:
        logger.warning("File %s does not match any configured source, skipping re-index", filepath)
        return

    try:
        chunks = parse_and_chunk(
            filepath, source_root,
            settings.chunk_size, settings.chunk_overlap,
        )

        if not chunks:
            tracking.remove_file(filepath)
            return

        texts = [c.content for c in chunks]
        embeddings = embed_texts(texts, settings.embedding_model, remote_config=settings.embedding_remote_config)
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
        event_bus.publish(IndexEvent(
            type="indexed", path=filepath,
            filename=_filename(filepath), chunks=len(chunks),
        ))

    except (OSError, ValueError, RuntimeError) as exc:
        tracking.mark_error(filepath, str(exc))
        logger.error("Failed to re-index %s: %s", filepath, exc)
        event_bus.publish(IndexEvent(
            type="error", path=filepath,
            filename=_filename(filepath), error=str(exc),
        ))


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
        self._debounce_lock = threading.Lock()

    def _should_process(self, path: str) -> bool:
        """Check if a file event should trigger re-indexing."""
        if not path.endswith(".md"):
            return False
        for pattern in self._settings.global_ignore:
            if fnmatch.fnmatch(path, pattern):
                return False
        now = time.time()
        with self._debounce_lock:
            last = self._debounce.get(path, 0)
            if now - last < 2.0:
                return False
            self._debounce[path] = now
            # Prune stale entries to prevent unbounded growth
            if len(self._debounce) > 1000:
                cutoff = now - 10.0
                self._debounce = {k: v for k, v in self._debounce.items() if v > cutoff}
        return True

    def _handle_file_change(self, event: FileSystemEvent):
        """Shared handler for file creation and modification events."""
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            reindex_file(
                event.src_path, self._settings,
                self._store, self._tracking,
            )

    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        self._handle_file_change(event)

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        self._handle_file_change(event)

    def on_moved(self, event: FileSystemEvent):
        """Handle file move/rename events, preserving embeddings when possible."""
        if event.is_directory:
            return
        src = str(Path(event.src_path).resolve())
        dest = str(Path(event.dest_path).resolve())

        # Renamed away from .md → treat as delete
        if src.endswith(".md") and not dest.endswith(".md"):
            logger.info("File renamed away from .md: %s → %s", src, dest)
            self._store.delete_by_source(src)
            self._tracking.remove_file(src)
            from app.tag_utils import notify_file_deleted
            notify_file_deleted(src)
            return

        # Renamed to .md → treat as new file
        if not src.endswith(".md") and dest.endswith(".md"):
            logger.info("File renamed to .md: %s → %s", src, dest)
            reindex_file(dest, self._settings, self._store, self._tracking)
            return

        # Both non-.md → ignore
        if not src.endswith(".md"):
            return

        # Find dest's source root
        dest_source_root = ""
        for s in self._settings.sources:
            resolved = str(Path(s).resolve())
            if dest.startswith(resolved + "/"):
                dest_source_root = resolved
                break

        # Dest is outside watched dirs → treat as delete
        if not dest_source_root:
            logger.info("File moved outside watched dirs: %s → %s", src, dest)
            self._store.delete_by_source(src)
            self._tracking.remove_file(src)
            from app.tag_utils import notify_file_deleted
            notify_file_deleted(src)
            return

        # Move within/between watched dirs: try to preserve embeddings
        old_record = self._tracking.get_file(src)
        if old_record and old_record["status"] == "complete":
            count = self._store.rename_source(src, dest, dest_source_root)
            self._tracking.rename_file(src, dest, dest_source_root)
            logger.info("File moved (preserved %d chunks): %s → %s",
                        count, src, dest)
        else:
            # Not indexed or incomplete: clean up old, index new
            self._store.delete_by_source(src)
            self._tracking.remove_file(src)
            reindex_file(dest, self._settings, self._store, self._tracking)

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events."""
        if event.is_directory:
            return
        if event.src_path.endswith(".md"):
            resolved = str(Path(event.src_path).resolve())
            logger.info("File deleted: %s", resolved)
            self._store.delete_by_source(resolved)
            self._tracking.remove_file(resolved)
            from app.tag_utils import notify_file_deleted
            notify_file_deleted(resolved)
            event_bus.publish(IndexEvent(
                type="deleted", path=resolved,
                filename=_filename(resolved),
            ))


class FileWatcher:
    """Manages the watchdog observer and allows runtime directory additions."""

    def __init__(
        self, settings: Settings, store: VectorStore,
        tracking: TrackingDB,
    ):
        self._handler = MarkdownHandler(settings, store, tracking)
        self._observer = Observer()
        self._watched: set[str] = set()
        self._settings = settings
        self._store = store
        self._tracking = tracking
        self._rescan_timer: threading.Timer | None = None
        self._rescan_interval: float = 60.0
        self._rescan_max_interval: float = 300.0

    def add_directory(self, path: str) -> bool:
        """Schedule a directory for watching.  Returns True if newly added."""
        source_path = Path(path).resolve()
        key = str(source_path)
        if key in self._watched:
            return False
        if not source_path.exists() or not source_path.is_dir():
            logger.warning("Cannot watch (not a directory): %s", source_path)
            return False
        self._observer.schedule(
            self._handler, key, recursive=True,
        )
        self._watched.add(key)
        logger.info("Watching: %s", source_path)
        return True

    def start(self):
        """Schedule all configured sources and start the observer."""
        for source in self._settings.sources:
            self.add_directory(source)
        self._observer.start()
        self._start_project_root_rescan()

    def stop(self):
        """Stop the observer and wait for it to finish."""
        if self._rescan_timer is not None:
            self._rescan_timer.cancel()
            self._rescan_timer = None
        self._observer.stop()
        self._observer.join()

    def _start_project_root_rescan(self):
        """Start periodic rescan for new project directories."""
        self._rescan_project_roots()

    def _rescan_project_roots(self):
        """Re-expand project roots and watch any newly discovered directories."""
        try:
            for source in self._settings.sources:
                if source not in self._watched:
                    if self.add_directory(source):
                        logger.info("Project root rescan: discovered new directory %s", source)
                        threading.Thread(
                            target=self.index_directory,
                            args=(source,),
                            daemon=True,
                        ).start()
            # Reset interval on success
            self._rescan_interval = 60.0
        except Exception:
            logger.exception("Error during project root rescan")
            # Back off on repeated errors (up to max interval)
            self._rescan_interval = min(
                self._rescan_interval * 2, self._rescan_max_interval,
            )
            logger.warning(
                "Next project root rescan in %.0fs (backoff)",
                self._rescan_interval,
            )
        # Schedule next rescan
        self._rescan_timer = threading.Timer(self._rescan_interval, self._rescan_project_roots)
        self._rescan_timer.daemon = True
        self._rescan_timer.start()

    def run_forever(self):
        """Block the current thread until interrupted."""
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def index_directory(self, path: str):
        """Trigger an initial index for files in a newly added directory."""
        from app.ingestion.indexer import index_directory
        index_directory(path, self._settings, self._store, self._tracking)


def start_watching(
    settings: Settings, store: VectorStore,
    tracking: TrackingDB,
) -> FileWatcher:
    """Start the file system observer for all configured sources.

    Returns the :class:`FileWatcher` instance so callers can add
    directories at runtime via :meth:`FileWatcher.add_directory`.
    """
    watcher = FileWatcher(settings, store, tracking)
    watcher.start()
    watcher.run_forever()
    return watcher
