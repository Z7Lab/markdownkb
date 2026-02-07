"""Settings and source management endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_settings
from app.ratelimit import HEAVY, LLM, STANDARD, limiter
from app.schemas import (
    AddSourceRequest,
    FeatureToggleRequest,
    IgnorePatternRequest,
    ModelInfoRequest,
    ProviderSettingsRequest,
    RefreshModelsRequest,
    RemoveSourceRequest,
    RetrievalSettingsRequest,
    SearchSummaryPromptRequest,
    SystemPromptRequest,
    TestConnectionRequest,
    TestPromptRequest,
)
from app.services.llm_service import (
    build_model_list,
    get_model_capabilities,
    ping_model,
    stream_test_prompt,
    test_llm_connection,
)
from app.utils import sse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["settings"])


# -- Sources --

@router.get("/sources")
@limiter.limit(STANDARD)
def get_sources(request: Request, settings: Settings = Depends(get_settings)):
    """Get list of source directories being watched."""
    return {"sources": settings.sources}


@router.post("/sources")
@limiter.limit(STANDARD)
def add_source(
    request: Request,
    req: AddSourceRequest,
    settings: Settings = Depends(get_settings),
):
    """Add a new source directory to watch."""
    settings.add_source(req.path)
    settings.save()
    return {"sources": settings.sources}


@router.delete("/sources")
@limiter.limit(STANDARD)
def remove_source(
    request: Request,
    req: RemoveSourceRequest,
    settings: Settings = Depends(get_settings),
):
    """Remove a source directory from watch list."""
    settings.remove_source(req.path)
    settings.save()
    return {"sources": settings.sources}


# -- Ignore Patterns --

@router.post("/ignore-patterns")
@limiter.limit(STANDARD)
def add_ignore_pattern(
    request: Request,
    req: IgnorePatternRequest,
    settings: Settings = Depends(get_settings),
):
    """Add a glob pattern to the ignore list."""
    settings.add_ignore_pattern(req.pattern)
    settings.save()
    return {"global_ignore": settings.global_ignore}


@router.delete("/ignore-patterns")
@limiter.limit(STANDARD)
def remove_ignore_pattern(
    request: Request,
    req: IgnorePatternRequest,
    settings: Settings = Depends(get_settings),
):
    """Remove a glob pattern from the ignore list."""
    settings.remove_ignore_pattern(req.pattern)
    settings.save()
    return {"global_ignore": settings.global_ignore}


# -- Settings --

@router.get("/settings")
@limiter.limit(STANDARD)
def get_settings_endpoint(request: Request, settings: Settings = Depends(get_settings)):
    """Get all application settings."""
    active_cfg = settings.get_active_llm_config()
    return {
        "active_provider": settings.active_provider,
        "providers": [
            {
                "name": p["name"],
                "model": p.get("model", ""),
                "api_base": p.get("api_base", ""),
            }
            for p in settings.llm_providers
        ],
        "features": settings.features,
        "mcp": settings.mcp_config,
        "sources": settings.sources,
        "global_ignore": settings.global_ignore,
        "active_model": active_cfg.get("model", ""),
        "active_api_base": active_cfg.get("api_base", ""),
        "system_prompt": settings.system_prompt,
        "default_system_prompt": settings.default_system_prompt,
        "search_summary_prompt": settings.search_summary_prompt,
        "default_search_summary_prompt": settings.default_search_summary_prompt,
        "embedding_model": settings.embedding_model,
        "intelligent_search_enabled": settings.intelligent_search_enabled,
        "top_k": settings.top_k,
        "default_top_k": settings.default_top_k,
        "score_threshold": settings.score_threshold,
        "default_score_threshold": settings.default_score_threshold,
        "hybrid_search": settings.hybrid_search,
        "default_hybrid_search": settings.default_hybrid_search,
        "bm25_weight": settings.bm25_weight,
        "default_bm25_weight": settings.default_bm25_weight,
    }


@router.put("/settings/provider")
@limiter.limit(STANDARD)
def save_provider(
    request: Request,
    req: ProviderSettingsRequest,
    settings: Settings = Depends(get_settings),
):
    """Save LLM provider configuration."""
    settings.active_provider = req.name
    for p in settings.llm_providers:
        if p.get("name") == req.name:
            p["model"] = req.model
            p["api_base"] = req.api_base
            break
    settings.save()
    return {"status": "saved"}


@router.post("/settings/test-connection")
@limiter.limit(LLM)
def test_connection(request: Request, req: TestConnectionRequest):
    """Test LLM provider connection."""
    result = test_llm_connection(
        req.name,
        req.model,
        req.api_base,
    )
    return {"result": result}


@router.post("/settings/ping-model")
@limiter.limit(LLM)
def ping_model_endpoint(request: Request, req: TestConnectionRequest):
    """Ping a specific model to check availability."""
    result = ping_model(req.model, req.api_base)
    return {"result": result}


@router.post("/settings/refresh-models")
@limiter.limit(HEAVY)
def refresh_models(request: Request, req: RefreshModelsRequest):
    """Refresh available models from provider."""
    models, status = build_model_list(
        req.name,
        req.api_base,
    )
    return {"models": models, "status": status}


@router.post("/settings/test-prompt")
@limiter.limit(LLM)
def test_prompt(
    request: Request,
    req: TestPromptRequest,
    settings: Settings = Depends(get_settings),
):
    """Test a prompt with the LLM using streaming."""
    if req.provider and req.model:
        model = req.model
        api_base = req.api_base or ""
    else:
        active = settings.get_active_llm_config()
        model = active.get("model", "")
        api_base = active.get("api_base", "") or ""

    if not model:
        raise HTTPException(status_code=400, detail="No model configured")

    def generate():
        try:
            for event, data in stream_test_prompt(
                req.prompt,
                model,
                api_base,
                settings.llm_temperature,
                settings.llm_max_tokens,
            ):
                yield sse(event, data)
        except (RuntimeError, ConnectionError, TimeoutError) as e:
            yield sse("error", {"message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


@router.post("/settings/model-info")
@limiter.limit(HEAVY)
def model_info(request: Request, req: ModelInfoRequest):
    """Get detailed information about a model."""
    return get_model_capabilities(req.model, req.api_base)


@router.put("/settings/features")
@limiter.limit(STANDARD)
def toggle_feature(
    request: Request,
    req: FeatureToggleRequest,
    settings: Settings = Depends(get_settings),
):
    """Toggle a feature flag on or off."""
    settings.features[req.name] = req.enabled
    settings.save()
    return {"status": "saved"}


@router.put("/settings/system-prompt")
@limiter.limit(STANDARD)
def update_system_prompt(
    request: Request,
    req: SystemPromptRequest,
    settings: Settings = Depends(get_settings),
):
    """Update the system prompt for chat."""
    settings.system_prompt = req.prompt
    settings.save()
    return {"status": "saved"}


@router.put("/settings/intelligent-search")
@limiter.limit(STANDARD)
def toggle_intelligent_search(
    request: Request,
    req: FeatureToggleRequest,
    settings: Settings = Depends(get_settings),
):
    """Toggle intelligent search (LLM query enhancement)."""
    settings.intelligent_search_enabled = req.enabled
    settings.save()
    return {"status": "saved"}


@router.put("/settings/search-summary-prompt")
@limiter.limit(STANDARD)
def update_search_summary_prompt(
    request: Request,
    req: SearchSummaryPromptRequest,
    settings: Settings = Depends(get_settings),
):
    """Update the search summary prompt."""
    settings.search_summary_prompt = req.prompt
    settings.save()
    return {"status": "saved"}


@router.put("/settings/retrieval")
@limiter.limit(STANDARD)
def update_retrieval_settings(
    request: Request,
    req: RetrievalSettingsRequest,
    settings: Settings = Depends(get_settings),
):
    """Update retrieval/search settings (hybrid search, weights, thresholds)."""
    settings.top_k = req.top_k
    settings.score_threshold = req.score_threshold
    settings.hybrid_search = req.hybrid_search
    settings.bm25_weight = req.bm25_weight
    settings.save()
    return {"status": "saved"}


# -- MCP Settings --

@router.get("/settings/mcp")
@limiter.limit(STANDARD)
def get_mcp_settings(request: Request, settings: Settings = Depends(get_settings)):
    """Get all MCP tool configurations."""
    return {"mcp": settings.mcp_config}


@router.get("/settings/mcp/{tool_name}")
@limiter.limit(STANDARD)
def get_mcp_tool_settings(
    request: Request,
    tool_name: str,
    settings: Settings = Depends(get_settings),
):
    """Get configuration for a specific MCP tool."""
    return {"config": settings.get_mcp_config(tool_name)}


@router.patch("/settings/mcp")
@limiter.limit(STANDARD)
def update_mcp_settings(
    request: Request,
    req: dict,
    settings: Settings = Depends(get_settings),
):
    """Update configuration for a specific MCP tool."""
    tool_name = req.get("tool_name")
    config = req.get("config")

    if not tool_name or config is None:
        raise HTTPException(
            status_code=400,
            detail="tool_name and config are required"
        )

    settings.set_mcp_config(tool_name, config)
    settings.save()
    return {"status": "saved", "tool_name": tool_name}


# -- Database Maintenance --

def get_path_size(path: Path) -> int:
    """Get total size of a file or directory in bytes.

    For SQLite database files, includes WAL and SHM files in the total.
    """
    if path.is_file():
        total = path.stat().st_size
        # Include SQLite WAL and SHM files if this is a .db file
        if path.suffix == '.db':
            wal_file = path.parent / f"{path.name}-wal"
            shm_file = path.parent / f"{path.name}-shm"
            if wal_file.exists():
                total += wal_file.stat().st_size
            if shm_file.exists():
                total += shm_file.stat().st_size
        return total
    if path.is_dir():
        return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
    return 0


@router.get("/settings/database-stats")
@limiter.limit(STANDARD)
def get_database_stats(
    request: Request,
    settings: Settings = Depends(get_settings),
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
            "tracking_path": str(data_dir / "mdkb.db"),
            "chroma_path": str(data_dir / "chromadb"),
            "size_bytes": (
                get_path_size(data_dir / "mdkb.db")
                + get_path_size(data_dir / "chromadb")
            ),
        },
    }
    return stats


@router.post("/settings/database/clear-chats")
@limiter.limit(STANDARD)
def clear_chat_history(request: Request):
    """Clear all chat history (threads and messages)."""
    chatdb = request.app.state.chatdb
    chatdb.clear_all()
    logger.info("Cleared all chat history")
    return {"status": "cleared", "database": "chats"}


@router.post("/settings/database/clear-searches")
@limiter.limit(STANDARD)
def clear_search_history(request: Request):
    """Clear all search history."""
    searchdb = request.app.state.searchdb
    searchdb.clear_all()
    logger.info("Cleared all search history")
    return {"status": "cleared", "database": "searches"}


@router.post("/settings/database/clear-vectors")
@limiter.limit(HEAVY)
def clear_vector_database(request: Request):
    """Clear vector database and file tracking, then trigger reindex."""
    vectorstore = request.app.state.store
    trackingdb = request.app.state.tracking

    # Clear both databases
    vectorstore.clear()
    trackingdb.clear()

    logger.info("Cleared vector database and file tracking")

    # Trigger reindex in background
    # Note: The actual reindexing will happen via the existing /api/index endpoint
    return {
        "status": "cleared",
        "database": "vectors",
        "message": "Vector database cleared. Use the reindex endpoint to rebuild.",
    }


@router.post("/settings/database/compact-chats")
@limiter.limit(STANDARD)
def compact_chat_database(request: Request):
    """Compact chat database by running VACUUM to reclaim disk space."""
    chatdb = request.app.state.chatdb
    chatdb.vacuum()
    logger.info("Compacted chat database")
    return {"status": "compacted", "database": "chats"}


@router.post("/settings/database/compact-searches")
@limiter.limit(STANDARD)
def compact_search_database(request: Request):
    """Compact search database by running VACUUM to reclaim disk space."""
    searchdb = request.app.state.searchdb
    searchdb.vacuum()
    logger.info("Compacted search database")
    return {"status": "compacted", "database": "searches"}
