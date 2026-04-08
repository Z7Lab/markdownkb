"""Buckets plugin — temporary scoped document collections with vector search."""

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


def _ensure_docs_bucket(svc) -> None:
    """Create the built-in documentation bucket if it doesn't exist.

    This gives new users a bucket they can chat with to learn the system.
    The bucket has no expiration — it's permanent but deletable.
    """
    # If it exists but is empty (interrupted previous creation), delete and recreate
    existing = svc._db.resolve(_DOCS_BUCKET_NAME)
    if existing:
        store = svc._get_store(existing["id"])
        if store.count > 0:
            return  # Already populated, nothing to do
        # Empty — previous creation was interrupted
        logger.info("Removing empty docs bucket from interrupted creation")
        svc.delete(existing["id"])

    # Also clean up any other empty bucket collections from interrupted startups


    # Skip if embedding model isn't installed yet
    from app.embeddings.downloader import is_installed
    from app.embeddings.registry import MODELS
    if not MODELS or not is_installed(svc._embedding_model):
        logger.debug("Skipping docs bucket — embedding model not installed yet")
        return

    docs_dir = _find_docs_dir()
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
