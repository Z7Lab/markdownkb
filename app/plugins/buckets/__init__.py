"""Buckets plugin — temporary scoped document collections with vector search."""

import hashlib
import logging
from pathlib import Path

from app.plugins.buckets.router import router

logger = logging.getLogger(__name__)

FEATURE_FLAG = "buckets"
_DOCS_BUCKET_NAME = "mdkb Documentation"

__all__ = ["FEATURE_FLAG", "router", "on_startup", "on_shutdown"]


def _find_docs_dir() -> Path | None:
    """Find the bundled docs directory.

    In Docker: /app/docs (copied into the image).
    Native: docs/ relative to the project root.
    """
    # Docker path
    docker_docs = Path("/app/docs")
    if docker_docs.is_dir() and any(docker_docs.glob("**/*.md")):
        return docker_docs

    # Native: relative to app package
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    native_docs = project_root / "docs"
    if native_docs.is_dir() and any(native_docs.glob("**/*.md")):
        return native_docs

    return None


def _hash_docs_dir(docs_dir: Path) -> str:
    """Hash all markdown files in a directory for change detection."""
    h = hashlib.sha256()
    for f in sorted(docs_dir.rglob("*.md")):
        h.update(f.name.encode())
        h.update(str(f.stat().st_size).encode())
        h.update(str(int(f.stat().st_mtime)).encode())
    return h.hexdigest()[:16]


# File that stores the hash of the docs used to build the bucket
_DOCS_HASH_FILE = ".docs_bucket_hash"


def _ensure_docs_bucket(svc) -> None:
    """Create or update the built-in documentation bucket.

    Creates on first startup. Recreates when docs change (detected via
    file hash). Handles interrupted creation (empty ChromaDB collection).
    The bucket has no expiration — permanent but deletable.
    """
    existing = svc._db.resolve(_DOCS_BUCKET_NAME)
    needs_rebuild = False

    if existing:
        store = svc._get_store(existing["id"])
        if store.count == 0:
            # Empty — previous creation was interrupted
            logger.info("Removing empty docs bucket from interrupted creation")
            svc.delete(existing["id"])
            existing = None
            needs_rebuild = True

    # Check if docs have changed since the bucket was built
    docs_dir = _find_docs_dir()
    if docs_dir and existing:
        from app.config import _default_data_dir
        hash_file = Path(_default_data_dir()) / _DOCS_HASH_FILE
        current_hash = _hash_docs_dir(docs_dir)
        stored_hash = ""
        try:
            stored_hash = hash_file.read_text().strip()
        except OSError:
            pass
        if current_hash != stored_hash:
            logger.info("Docs changed (hash %s → %s), rebuilding docs bucket", stored_hash[:8] or "none", current_hash[:8])
            svc.delete(existing["id"])
            existing = None
            needs_rebuild = True

    if existing and not needs_rebuild:
        return  # Up to date

    # Skip if embedding model isn't installed yet
    from app.embeddings.downloader import is_installed
    from app.embeddings.registry import MODELS
    if not MODELS or not is_installed(svc._embedding_model):
        logger.debug("Skipping docs bucket — embedding model not installed yet")
        return

    if not docs_dir:
        logger.debug("Skipping docs bucket — docs directory not found")
        return

    try:
        logger.info("Creating built-in docs bucket from %s...", docs_dir)
        record = svc.create(
            name=_DOCS_BUCKET_NAME,
            sources=[{"path": str(docs_dir), "glob": "**/*.md"}],
            expires_in=None,
        )
        logger.info(
            "Created built-in docs bucket: %d files, %d chunks",
            record["file_count"], record["chunk_count"],
        )
        # Save hash so we can detect changes on next startup
        try:
            from app.config import _default_data_dir
            hash_file = Path(_default_data_dir()) / _DOCS_HASH_FILE
            hash_file.write_text(_hash_docs_dir(docs_dir))
        except OSError:
            pass
    except ValueError as e:
        logger.debug("Docs bucket already exists: %s", e)
    except Exception:
        logger.exception("Failed to create docs bucket")


def on_startup(app) -> None:
    """Initialize BucketDB and BucketService, clean up expired buckets."""
    from app.plugins.buckets.bucket_service import BucketService
    from app.plugins.buckets.bucketdb import BucketDB

    settings = app.state.settings
    bucketdb = BucketDB(settings.data_directory)
    app.state.bucketdb = bucketdb

    chromadb_dir = str(settings.persist_directory)
    svc = BucketService(bucketdb, chromadb_dir, settings.embedding_model, remote_config=settings.embedding_remote_config)
    app.state.bucket_service = svc

    # Clean up expired buckets on startup
    cleaned = svc.cleanup_expired()
    if cleaned:
        logger.info("Cleaned up %d expired bucket(s) on startup", cleaned)

    # Create the built-in documentation bucket on first run (background)
    import threading
    threading.Thread(
        target=_ensure_docs_bucket, args=(svc,),
        daemon=True, name="docs-bucket-init",
    ).start()


def on_shutdown(app) -> None:
    """Close BucketDB connection."""
    bucketdb = getattr(app.state, "bucketdb", None)
    if bucketdb:
        bucketdb.close()
