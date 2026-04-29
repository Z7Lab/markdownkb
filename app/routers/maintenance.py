"""Database maintenance, logging, and stats endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request

from app.config import Settings
from app.deps import get_bucket_service, get_chatdb, get_searchdb, get_settings, get_store, get_tracking
from app.ratelimit import HEAVY, STANDARD, limiter
from app.logbuffer import log_buffer
from app.schemas.misc import LoggerOverridesRequest, LogLevelRequest
from app.text import get_path_size

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["maintenance"])


# -- Database Stats --

@router.get("/settings/database-stats")
@limiter.limit(STANDARD)
def get_database_stats(
    request: Request,
    settings: Settings = Depends(get_settings),
    tracking=Depends(get_tracking),
    store=Depends(get_store),
    bucket_service=Depends(get_bucket_service),
):
    """Get statistics for all databases."""
    data_dir = Path(settings.data_directory)

    stats = {
        "chat_history": {
            "path": str(data_dir / "chats.db"),
            "size_bytes": get_path_size(data_dir / "chats.db"),
        },
        "search_history": {
            "path": str(data_dir / "searches.db"),
            "size_bytes": get_path_size(data_dir / "searches.db"),
        },
        "vector_database": {
            "tracking_path": str(data_dir / "markdownkb.db"),
            "chroma_path": str(data_dir / "chromadb"),
            "size_bytes": (
                get_path_size(data_dir / "markdownkb.db")
                + get_path_size(data_dir / "chromadb")
            ),
        },
    }

    # Add index counts from tracking DB and vector store (via DI).
    # Exclude bucket-assigned files — they appear in the Buckets tab, not Files tab,
    # so the count here matches what the user sees in the Files tab.
    all_files = tracking.get_all_files()
    if bucket_service:
        bucketed = bucket_service.db.get_bucketed_paths()
        all_files = [f for f in all_files if f["path"] not in bucketed]
    indexed_files = [f for f in all_files if f["status"] == "complete"]
    total_chunks = sum(f.get("chunk_count", 0) for f in indexed_files)
    stats["vector_database"]["indexed_files"] = len(indexed_files)
    stats["vector_database"]["total_files"] = len(all_files)
    stats["vector_database"]["total_chunks"] = total_chunks
    stats["vector_database"]["vector_count"] = store.count
    stats["vector_database"]["embedding_model"] = settings.embedding_model
    stats["vector_database"]["data_directory"] = str(data_dir)

    # Plugin-owned databases — enumerate all .db files not already listed
    known = {"chats.db", "searches.db", "markdownkb.db"}
    plugin_dbs = []
    for db_path in sorted(data_dir.glob("*.db")):
        if db_path.name not in known:
            plugin_dbs.append({
                "name": db_path.stem,
                "path": str(db_path),
                "size_bytes": get_path_size(db_path),
            })
    if plugin_dbs:
        stats["plugin_databases"] = plugin_dbs

    return stats


# -- Clear Operations --

@router.post("/settings/database/clear-chats")
@limiter.limit(STANDARD)
def clear_chat_history(request: Request, chatdb=Depends(get_chatdb)):
    """Clear all chat history (threads and messages)."""
    chatdb.clear_all()
    logger.info("Cleared all chat history")
    return {"status": "cleared", "database": "chats"}


@router.post("/settings/database/clear-searches")
@limiter.limit(STANDARD)
def clear_search_history(request: Request, searchdb=Depends(get_searchdb)):
    """Clear all search history."""
    searchdb.clear_all()
    logger.info("Cleared all search history")
    return {"status": "cleared", "database": "searches"}


@router.post("/settings/database/clear-vectors")
@limiter.limit(HEAVY)
def clear_vector_database(
    request: Request,
    vectorstore=Depends(get_store),
    trackingdb=Depends(get_tracking),
):
    """Clear vector database and file tracking, then trigger reindex."""
    vectorstore.clear()
    trackingdb.clear()

    logger.info("Cleared vector database and file tracking")

    return {
        "status": "cleared",
        "database": "vectors",
        "message": "Vector database cleared. Use the reindex endpoint to rebuild.",
    }


# -- Vector Maintenance --

@router.get("/settings/database/maintenance-preview")
@limiter.limit(STANDARD)
def get_maintenance_preview(
    request: Request,
    settings: Settings = Depends(get_settings),
    store=Depends(get_store),
):
    """Scan for reclaimable space without modifying anything.

    Returns counts and byte estimates for:
    - Orphaned ChromaDB chunks (source file deleted from disk)
    - Orphaned HNSW segment directories (leftover from deleted collections/buckets)
    - SQLite free pages reclaimable by VACUUM
    """
    from app.storage.chromadb_maintenance import (
        estimate_vacuum_savings,
        get_orphaned_chunk_info,
        get_orphaned_segment_dirs,
    )

    chroma_dir = str(Path(settings.data_directory) / "chromadb")
    orphan_ids, orphan_sources = get_orphaned_chunk_info(store._collection)
    orphan_dirs = get_orphaned_segment_dirs(chroma_dir)
    orphan_dirs_bytes = sum(size for _, size in orphan_dirs)
    vacuum_estimate = estimate_vacuum_savings(chroma_dir)

    return {
        "orphaned_chunks": len(orphan_ids),
        "orphaned_chunk_sources": len(orphan_sources),
        "orphaned_segment_dirs": len(orphan_dirs),
        "orphaned_segment_dirs_bytes": orphan_dirs_bytes,
        "vacuum_estimate_bytes": vacuum_estimate,
        "total_reclaimable_bytes": orphan_dirs_bytes + vacuum_estimate,
    }


@router.post("/settings/database/cleanup-orphans")
@limiter.limit(HEAVY)
def cleanup_orphan_chunks(
    request: Request,
    tracking=Depends(get_tracking),
    store=Depends(get_store),
):
    """Delete ChromaDB chunks whose source files no longer exist on disk.

    Also removes the corresponding tracking DB rows so file counts stay
    consistent with what is actually indexed.
    """
    from app.storage.chromadb_maintenance import get_orphaned_chunk_info

    orphan_ids, orphan_sources = get_orphaned_chunk_info(store._collection)
    if orphan_ids:
        batch_size = 500
        for i in range(0, len(orphan_ids), batch_size):
            store._collection.delete(ids=orphan_ids[i:i + batch_size])
        for src in orphan_sources:
            tracking.remove_file(src)
        logger.info(
            "Orphan cleanup: deleted %d chunks from %d source paths",
            len(orphan_ids), len(orphan_sources),
        )
    return {
        "status": "ok",
        "deleted_chunks": len(orphan_ids),
        "deleted_files": len(orphan_sources),
    }


@router.post("/settings/database/compact-vectors")
@limiter.limit(HEAVY)
def compact_vector_database(
    request: Request,
    settings: Settings = Depends(get_settings),
):
    """VACUUM chroma.sqlite3 and delete orphaned HNSW segment directories.

    Orphaned segment dirs are UUID directories left behind when collections
    or buckets are deleted — ChromaDB never removes them automatically.
    VACUUM reclaims SQLite free pages accumulated after bulk deletes.
    """
    from app.storage.chromadb_maintenance import delete_orphaned_segments, vacuum_chromadb
    from app.config.docker import in_docker

    chroma_dir = str(Path(settings.data_directory) / "chromadb")
    deleted_dirs, dirs_freed = delete_orphaned_segments(chroma_dir)
    vacuum_ok, vacuum_freed = vacuum_chromadb(chroma_dir)

    logger.info(
        "Vector compact: deleted %d orphaned segment dirs (%d bytes); vacuum=%s freed=%d bytes",
        deleted_dirs, dirs_freed, vacuum_ok, vacuum_freed,
    )
    return {
        "status": "ok",
        "deleted_segment_dirs": deleted_dirs,
        "segment_dirs_freed_bytes": dirs_freed,
        "vacuum_success": vacuum_ok,
        "vacuum_freed_bytes": vacuum_freed,
        "total_freed_bytes": dirs_freed + vacuum_freed,
        "is_docker": in_docker(),
    }


# -- Compact Operations --

@router.post("/settings/database/compact-chats")
@limiter.limit(STANDARD)
def compact_chat_database(request: Request, chatdb=Depends(get_chatdb)):
    """Compact chat database by running VACUUM to reclaim disk space."""
    chatdb.vacuum()
    logger.info("Compacted chat database")
    return {"status": "compacted", "database": "chats"}


@router.post("/settings/database/compact-searches")
@limiter.limit(STANDARD)
def compact_search_database(request: Request, searchdb=Depends(get_searchdb)):
    """Compact search database by running VACUUM to reclaim disk space."""
    searchdb.vacuum()
    logger.info("Compacted search database")
    return {"status": "compacted", "database": "searches"}


# -- Logging --

@router.get("/settings/log-level")
@limiter.limit(STANDARD)
def get_log_level(request: Request, settings: Settings = Depends(get_settings)):
    """Get the current logging level."""
    current = logging.getLogger().level
    level = "OFF" if current >= 60 else settings.log_level
    return {"level": level}


@router.put("/settings/log-level")
@limiter.limit(STANDARD)
def set_log_level(
    request: Request,
    req: LogLevelRequest,
    settings: Settings = Depends(get_settings),
):
    """Set the logging level (INFO, DEBUG, or OFF) and persist to config."""
    from app.log_overrides import apply_log_overrides
    level = 60 if req.level == "OFF" else getattr(logging, req.level, logging.INFO)
    logging.getLogger().setLevel(level)
    settings.log_level = req.level
    settings.save()
    apply_log_overrides(settings)
    logger.info("Log level changed to %s", req.level)
    return {"status": "saved", "level": req.level}


@router.get("/settings/log-overrides")
@limiter.limit(STANDARD)
def get_log_overrides(request: Request, settings: Settings = Depends(get_settings)):
    """Return plugin-declared logging defaults and user-defined overrides."""
    from app.log_overrides import get_plugin_defaults
    return {
        "user": settings.logger_overrides,
        "plugin_defaults": get_plugin_defaults(),
    }


@router.put("/settings/log-overrides")
@limiter.limit(STANDARD)
def set_log_overrides(
    request: Request,
    req: LoggerOverridesRequest,
    settings: Settings = Depends(get_settings),
):
    """Persist user-defined per-logger overrides and apply them immediately."""
    from app.log_overrides import apply_log_overrides
    settings.logger_overrides = req.overrides
    settings.save()
    apply_log_overrides(settings)
    return {"status": "saved"}


@router.get("/settings/logs")
@limiter.limit(STANDARD)
def get_logs(request: Request, since: int = 0):
    """Get log entries from the ring buffer.

    Query param `since` is the sequence number from the last poll.
    Returns only new entries since that sequence.
    """
    entries, seq = log_buffer.get_entries(since)
    return {"entries": entries, "seq": seq}


@router.delete("/settings/logs")
@limiter.limit(STANDARD)
def clear_logs(request: Request):
    """Clear all log entries from the ring buffer."""
    log_buffer.clear()
    return {"status": "cleared"}
