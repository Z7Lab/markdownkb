"""Health and stats endpoints."""

import queue

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_settings, get_store, get_tracking
from app.events import event_bus
from app.ratelimit import STANDARD, limiter
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore
from app.utils import sse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
@limiter.limit(STANDARD)
def health(request: Request, store: VectorStore = Depends(get_store)):
    degraded = getattr(request.app.state, "embedding_model_degraded", False)
    using_defaults = getattr(request.app.state, "using_default_config", False)
    result = {
        "status": "degraded" if degraded else "ok",
        "chunks": store.count,
    }
    if degraded:
        result["embedding_model_degraded"] = True
    if using_defaults:
        result["using_defaults"] = True
    return result


@router.get("/health/llm")
@limiter.limit(STANDARD)
def llm_health(request: Request, settings: Settings = Depends(get_settings)):
    """Lightweight LLM health check (for status polling)."""
    active_cfg = settings.get_active_llm_config()
    return {
        "provider": settings.active_provider,
        "model": active_cfg.get("model", ""),
        "api_base": active_cfg.get("api_base", ""),
        "configured": bool(active_cfg.get("model")),
    }


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


@router.get("/index/events")
@limiter.limit(STANDARD)
def index_events(request: Request):
    """SSE stream of real-time index events (file indexed/deleted/error)."""
    try:
        sub = event_bus.subscribe()
    except RuntimeError:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            {"detail": "Too many concurrent SSE connections"},
            status_code=429,
        )

    def generate():
        try:
            # Send initial heartbeat so the client knows it's connected
            yield sse("connected", {"status": "ok"})
            while True:
                try:
                    event = sub.get(timeout=30)
                    if event is None:
                        break
                    yield sse("index", event.to_dict())
                except queue.Empty:
                    # Send keepalive comment to prevent timeout
                    yield ": keepalive\n\n"
        finally:
            event_bus.unsubscribe(sub)

    return StreamingResponse(generate(), media_type="text/event-stream")
