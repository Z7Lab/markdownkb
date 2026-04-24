"""Buckets plugin — temporary scoped document collections with vector search."""

import hashlib
import logging
from pathlib import Path

from app.plugins.buckets.router import router

logger = logging.getLogger(__name__)

FEATURE_FLAG = "buckets"
_DOCS_BUCKET_NAME = "MarkdownKB Documentation"

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
    """Hash all markdown files in a directory by content.

    Uses file content (not mtime) so Docker rebuilds, which copy files
    into a fresh image with a new mtime, don't falsely invalidate the
    bucket. Identical content ⇒ identical hash ⇒ bucket stays as-is.
    """
    h = hashlib.sha256()
    for f in sorted(docs_dir.rglob("*.md")):
        h.update(b"\0")
        h.update(str(f.relative_to(docs_dir)).encode())
        h.update(b"\0")
        try:
            h.update(f.read_bytes())
        except OSError:
            # If a file becomes unreadable mid-scan, still produce a
            # deterministic hash by mixing in just its path.
            continue
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
        store = svc.get_store(existing["id"])
        if store.count == 0:
            # Empty — previous creation was interrupted
            logger.info("Removing empty docs bucket from interrupted creation")
            svc.delete(existing["id"])
            existing = None
            needs_rebuild = True

    # Check if docs have changed since the bucket was built
    docs_dir = _find_docs_dir()
    if docs_dir and existing:
        from app.config import default_data_dir as _default_data_dir
        hash_file = Path(_default_data_dir()) / _DOCS_HASH_FILE
        current_hash = _hash_docs_dir(docs_dir)
        stored_hash = ""
        try:
            stored_hash = hash_file.read_text().strip()
        except FileNotFoundError:
            pass  # Expected on first run — no hash file yet
        except OSError as e:
            logger.warning("Could not read docs hash file %s: %s", hash_file, e)
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
            from app.config import default_data_dir as _default_data_dir
            hash_file = Path(_default_data_dir()) / _DOCS_HASH_FILE
            hash_file.write_text(_hash_docs_dir(docs_dir))
        except OSError as e:
            logger.warning(
                "Could not save docs hash file — bucket will be rebuilt on next startup: %s", e
            )
    except ValueError as e:
        logger.debug("Docs bucket already exists: %s", e)
    except Exception:
        logger.exception("Failed to create docs bucket")


def _sync_missing_bucket_mounts(svc, settings) -> None:
    """Ensure every bucket source path has a Docker volume mount configured.

    Paths not accessible inside Docker indicate a missing mount entry. Adding them
    here and rewriting compose.override.yml means the user only needs one more
    `make docker-down && make docker-up` to recover.
    """
    import json as _json
    from app.config.docker import in_docker, write_compose_override

    if not in_docker():
        return

    changed = False
    for bucket in svc.db.list_all():
        sources = _json.loads(bucket.get("sources", "[]"))
        for src in sources:
            raw = src.get("path", "")
            if not raw:
                continue
            resolved = str(Path(raw).resolve())
            if not Path(resolved).exists() and settings.add_bucket_mount(resolved):
                logger.info("Added missing bucket mount to config: %s — restart Docker to apply", resolved)
                changed = True

    if changed:
        settings.save()
        try:
            project_root = settings.project_root
            all_configs = (
                settings.source_configs
                + settings.project_root_source_configs
                + settings.bucket_mount_configs
            )
            write_compose_override(all_configs, project_root)
        except Exception:
            logger.debug("Could not sync compose.override.yml for bucket mounts", exc_info=True)


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

    # Ensure every bucket source path is represented in Docker mounts config.
    _sync_missing_bucket_mounts(svc, settings)

    # Flag newly expired buckets on startup (does not delete them)
    flagged = svc.flag_expired()
    if flagged:
        logger.info("Flagged %d expired bucket(s) on startup", flagged)

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
