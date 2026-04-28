"""Health and stats endpoints."""

import os
import queue
import stat

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_settings, get_store, get_tracking
from app.events import event_bus
from app.ratelimit import STANDARD, limiter
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore
from app.transport import sse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
@limiter.limit(STANDARD)
def health(request: Request, store: VectorStore = Depends(get_store)):
    embedding_missing = getattr(request.app.state, "embedding_model_missing", False)
    using_defaults = getattr(request.app.state, "using_default_config", False)
    auth_enabled = getattr(request.app.state, "auth_enabled", True)
    network_exposed = getattr(request.app.state, "network_exposed", False)
    result = {
        "status": "ok",
        "chunks": store.count,
        "auth_enabled": auth_enabled,
        "network_exposed": network_exposed,
    }
    if embedding_missing:
        result["embedding_model_missing"] = True
    if using_defaults:
        result["using_defaults"] = True
    return result


@router.get("/settings/security-check")
@limiter.limit(STANDARD)
def security_check(request: Request, settings: Settings = Depends(get_settings)):
    """Structured security checklist — accessible without auth (same as /health)."""
    auth_enabled = getattr(request.app.state, "auth_enabled", True)
    network_exposed = getattr(request.app.state, "network_exposed", False)
    api_key: str = getattr(request.app.state, "api_key", "") or ""

    # API key strength: none / weak (< 16 chars) / ok
    if not api_key:
        api_key_strength = "none"
    elif len(api_key) < 16:
        api_key_strength = "weak"
    else:
        api_key_strength = "ok"

    # Data directory world-readable check
    data_dir = settings.data_directory
    data_dir_world_readable = False
    try:
        mode = os.stat(data_dir).st_mode
        data_dir_world_readable = bool(mode & stat.S_IROTH)
    except OSError:
        pass

    # MCP enabled in settings (separate process — flag if any feature is on)
    mcp_features = settings.mcp_features
    mcp_enabled = any(mcp_features.values()) if mcp_features else False

    return {
        "auth_enabled": auth_enabled,
        "network_exposed": network_exposed,
        "api_key_strength": api_key_strength,
        "data_dir_world_readable": data_dir_world_readable,
        "mcp_enabled": mcp_enabled,
    }


@router.get("/health/llm")
@limiter.limit(STANDARD)
def llm_health(request: Request, settings: Settings = Depends(get_settings)):
    """Lightweight LLM health check (for status polling)."""
    active_cfg = settings.get_active_llm_config()
    configured = bool(active_cfg.get("model"))
    provider = settings.active_provider
    api_base = active_cfg.get("api_base", "")

    # Lightweight reachability probe for local providers.
    # Cloud providers are assumed reachable when configured (avoids API costs).
    reachable = False
    if configured:
        if "ollama" in provider.lower() and api_base:
            from app.plugins.catalogs.ollama.catalog import is_reachable
            reachable = is_reachable(api_base)
        else:
            reachable = configured  # trust cloud config

    return {
        "provider": provider,
        "model": active_cfg.get("model", ""),
        "api_base": api_base,
        "configured": configured,
        "reachable": reachable,
        "provider_fallback": active_cfg.get("_fallback", False),
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
                    event = sub.get(timeout=15)
                    if event is None:
                        break
                    yield sse("index", event.to_dict())
                except queue.Empty:
                    # Send keepalive comment to prevent timeout
                    yield ": keepalive\n\n"
        finally:
            event_bus.unsubscribe(sub)

    return StreamingResponse(generate(), media_type="text/event-stream")
