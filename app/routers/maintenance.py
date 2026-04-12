"""Database maintenance, logging, and stats endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request

from app.config import Settings
from app.deps import get_chatdb, get_searchdb, get_settings, get_store, get_tracking
from app.ratelimit import HEAVY, STANDARD, limiter
from app.logbuffer import log_buffer
from app.schemas import LogLevelRequest
from app.utils import get_path_size

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["maintenance"])


# -- Database Stats --

@router.get("/settings/database-stats")
@limiter.limit(STANDARD)
def get_database_stats(
    request: Request,
    settings: Settings = Depends(get_settings),
    tracking=Depends(get_tracking),
    store=Depends(get_store),
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

    # Add index counts from tracking DB and vector store (via DI)
    all_files = tracking.get_all_files()
    indexed_files = [f for f in all_files if f["status"] == "complete"]
    total_chunks = sum(f.get("chunk_count", 0) for f in indexed_files)
    stats["vector_database"]["indexed_files"] = len(indexed_files)
    stats["vector_database"]["total_files"] = len(all_files)
    stats["vector_database"]["total_chunks"] = total_chunks
    stats["vector_database"]["vector_count"] = store.count
    stats["vector_database"]["embedding_model"] = settings.embedding_model
    stats["vector_database"]["data_directory"] = str(data_dir)

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
    level = 60 if req.level == "OFF" else getattr(logging, req.level, logging.INFO)
    logging.getLogger().setLevel(level)
    settings.log_level = req.level
    settings.save()
    logger.info("Log level changed to %s", req.level)
    return {"status": "saved", "level": req.level}


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
