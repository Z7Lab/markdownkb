"""File system watcher for automatic re-indexing on changes."""

import fnmatch
import json
import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from app.config import Settings
from app.embeddings.embedder import embed_texts
from app.ingestion.parser import parse_and_chunk
from app.ingestion.scanner import compute_file_hash, scan_sources
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)

HASH_CACHE_FILE = "file_hashes.json"


class HashCache:
    """Persistent cache mapping file paths to content hashes."""

    def __init__(self, data_dir: str):
        self._path = Path(data_dir) / HASH_CACHE_FILE
        self._hashes: dict[str, str] = {}
        self._load()

    def _load(self):
        """Load the hash cache from disk."""
        if self._path.exists():
            try:
                self._hashes = json.loads(self._path.read_text())
            except json.JSONDecodeError:
                self._hashes = {}

    def save(self):
        """Persist the hash cache to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._hashes, indent=2))

    def get(self, filepath: str) -> str | None:
        """Return the stored hash for a file path, or None."""
        return self._hashes.get(filepath)

    def set(self, filepath: str, hash_val: str):
        """Store a hash value for a file path."""
        self._hashes[filepath] = hash_val

    def remove(self, filepath: str):
        """Remove a file path from the cache."""
        self._hashes.pop(filepath, None)

    def has_changed(self, filepath: str) -> bool:
        """Return True if the file's current hash differs from the stored one."""
        if not Path(filepath).exists():
            return True
        current = compute_file_hash(filepath)
        stored = self.get(filepath)
        return current != stored


def reindex_file(filepath: str, settings: Settings, store: VectorStore,
                 hash_cache: HashCache):
    """Re-index a single markdown file, updating the vector store."""
    filepath = str(Path(filepath).resolve())

    if not filepath.endswith(".md"):
        return

    if not Path(filepath).exists():
        logger.info("File deleted, removing from index: %s", filepath)
        store.delete_by_source(filepath)
        hash_cache.remove(filepath)
        hash_cache.save()
        return

    if not hash_cache.has_changed(filepath):
        logger.debug("File unchanged, skipping: %s", filepath)
        return

    logger.info("Re-indexing: %s", filepath)

    # Remove old chunks
    store.delete_by_source(filepath)

    # Parse and chunk
    source_root = ""
    for src in settings.sources:
        if filepath.startswith(str(Path(src).resolve())):
            source_root = str(Path(src).resolve())
            break

    chunks = parse_and_chunk(filepath, source_root,
                             settings.chunk_size, settings.chunk_overlap)

    if not chunks:
        hash_cache.remove(filepath)
        hash_cache.save()
        return

    texts = [c.content for c in chunks]
    embeddings = embed_texts(texts)
    ids = [c.chunk_id for c in chunks]
    metadatas = [c.metadata for c in chunks]

    store.add(ids, texts, embeddings, metadatas)

    new_hash = compute_file_hash(filepath)
    hash_cache.set(filepath, new_hash)
    hash_cache.save()

    logger.info("Re-indexed %s: %d chunks", filepath, len(chunks))


class MarkdownHandler(FileSystemEventHandler):
    """Watchdog event handler that triggers re-indexing for markdown files."""

    def __init__(self, settings: Settings, store: VectorStore,
                 hash_cache: HashCache):
        self._settings = settings
        self._store = store
        self._hash_cache = hash_cache
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
        if now - last < 2.0:  # 2 second debounce
            return False
        self._debounce[path] = now
        return True

    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            reindex_file(event.src_path, self._settings, self._store,
                         self._hash_cache)

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            reindex_file(event.src_path, self._settings, self._store,
                         self._hash_cache)

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events."""
        if event.is_directory:
            return
        if event.src_path.endswith(".md"):
            logger.info("File deleted: %s", event.src_path)
            self._store.delete_by_source(str(Path(event.src_path).resolve()))
            self._hash_cache.remove(str(Path(event.src_path).resolve()))
            self._hash_cache.save()


def start_watching(settings: Settings, store: VectorStore):
    """Start the file system observer for all configured source directories."""
    hash_cache = HashCache(settings.persist_directory)
    handler = MarkdownHandler(settings, store, hash_cache)
    observer = Observer()

    for source in settings.sources:
        source_path = Path(source).resolve()
        if source_path.exists() and source_path.is_dir():
            observer.schedule(handler, str(source_path), recursive=True)
            logger.info("Watching: %s", source_path)

    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


def smart_reindex(settings: Settings, store: VectorStore) -> str:
    """Re-index only files whose content has changed since last index."""
    hash_cache = HashCache(settings.persist_directory)
    files = scan_sources(settings.sources, settings.global_ignore)
    changed = 0
    skipped = 0

    for fi in files:
        if hash_cache.has_changed(fi.path):
            reindex_file(fi.path, settings, store, hash_cache)
            changed += 1
        else:
            skipped += 1

    return (f"Smart re-index complete. "
            f"Changed: {changed}, Skipped (unchanged): {skipped}, "
            f"Total store: {store.count}")
