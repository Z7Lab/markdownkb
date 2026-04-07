"""Buckets plugin — temporary scoped document collections with vector search."""

import logging

from app.plugins.buckets.router import router

logger = logging.getLogger(__name__)

FEATURE_FLAG = "buckets"

__all__ = ["FEATURE_FLAG", "router", "on_startup", "on_shutdown"]


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


def on_shutdown(app) -> None:
    """Close BucketDB connection."""
    bucketdb = getattr(app.state, "bucketdb", None)
    if bucketdb:
        bucketdb.close()
