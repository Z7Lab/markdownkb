"""Health and stats endpoints."""

from fastapi import APIRouter, Depends, Request

from app.config import Settings
from app.deps import get_settings, get_store, get_tracking
from app.ratelimit import STANDARD, limiter
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
@limiter.limit(STANDARD)
def health(request: Request, store: VectorStore = Depends(get_store)):
    return {"status": "ok", "chunks": store.count}


@router.get("/stats")
@limiter.limit(STANDARD)
def stats(
    request: Request,
    settings: Settings = Depends(get_settings),
    store: VectorStore = Depends(get_store),
    tracking: TrackingDB = Depends(get_tracking),
):
    db_stats = tracking.get_stats()
    return {
        "sources": settings.sources,
        "files_tracked": db_stats["total_files"],
        "files_complete": db_stats["complete"],
        "files_error": db_stats["error"],
        "chunks_indexed": store.count,
        "embedding_model": settings.embedding_model,
        "active_provider": settings.active_provider,
    }
