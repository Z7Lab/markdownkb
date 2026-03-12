"""Settings and source management endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_cancel_event, get_chatdb, get_searchdb, get_settings, get_store, get_tracking, get_watcher
from app.ratelimit import HEAVY, LLM, STANDARD, limiter
from app.logbuffer import log_buffer
from app.schemas import (
    AddProjectRootRequest,
    AddSourceRequest,
    FeatureToggleRequest,
    IgnorePatternRequest,
    LlmParamsRequest,
    LogLevelRequest,
    McpToolConfigRequest,
    ModelInfoRequest,
    ProviderSettingsRequest,
    RefreshModelsRequest,
    RemoveProjectRootRequest,
    RemoveSourceRequest,
    RetrievalSettingsRequest,
    SearchSummaryPromptRequest,
    SystemPromptRequest,
    TestConnectionRequest,
    TestPromptRequest,
    UpdateProjectRootRequest,
)
from app.services.llm_service import (
    build_model_list,
    get_model_capabilities,
    ping_model,
    stream_test_prompt,
    test_llm_connection,
)
from app.utils import get_path_size, sse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["settings"])


def _watch_and_index(watcher, path: str):
    """If the watcher is active, add a directory and index in background."""
    if watcher is None:
        return
    resolved = str(Path(path).resolve())
    if watcher.add_directory(resolved):
        import threading
        threading.Thread(
            target=watcher.index_directory,
            args=(resolved,),
            daemon=True,
        ).start()


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
    watcher=Depends(get_watcher),
):
    """Add a new source directory to watch.

    When the file watcher is running, the new directory is immediately
    watched and its files are indexed — no restart required.
    """
    settings.add_source(req.path)
    settings.save()
    _watch_and_index(watcher, req.path)
    return {"sources": settings.sources}


@router.delete("/sources")
@limiter.limit(STANDARD)
def remove_source(
    request: Request,
    req: RemoveSourceRequest,
    settings: Settings = Depends(get_settings),
    tracking=Depends(get_tracking),
    store=Depends(get_store),
):
    """Remove a source directory from watch list.

    When cleanup=true, also unindexes all files that were under this source.
    """
    resolved = str(Path(req.path).resolve())
    removed_count = 0

    if req.cleanup:
        all_files = tracking.get_all_files()
        for f in all_files:
            fpath = f["path"]
            if fpath.startswith(resolved + "/") or fpath.startswith(req.path + "/"):
                store.delete_by_source(fpath)
                tracking.unindex_file(fpath)
                removed_count += 1

    settings.remove_source(req.path)
    settings.save()
    return {"sources": settings.sources, "unindexed_count": removed_count}


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


# -- Project Roots --

@router.get("/project-roots")
@limiter.limit(STANDARD)
def get_project_roots(request: Request, settings: Settings = Depends(get_settings)):
    """Get list of configured project roots."""
    return {"project_roots": settings.project_roots}


@router.post("/project-roots")
@limiter.limit(STANDARD)
def add_project_root(
    request: Request,
    req: AddProjectRootRequest,
    settings: Settings = Depends(get_settings),
    watcher=Depends(get_watcher),
):
    """Add a project root directory.

    The project root is scanned for subdirectories containing files that
    match the include patterns.  Each matching project is watched and
    indexed automatically.
    """
    settings.add_project_root(req.path, req.include, req.exclude)
    settings.save()
    for source in settings.sources:
        _watch_and_index(watcher, source)
    return {"project_roots": settings.project_roots}


@router.put("/project-roots")
@limiter.limit(STANDARD)
def update_project_root(
    request: Request,
    req: UpdateProjectRootRequest,
    settings: Settings = Depends(get_settings),
    watcher=Depends(get_watcher),
):
    """Update include/exclude patterns for a project root."""
    try:
        settings.update_project_root(req.path, req.include, req.exclude)
    except KeyError:
        raise HTTPException(404, f"Project root not found: {req.path}")
    settings.save()
    for source in settings.sources:
        _watch_and_index(watcher, source)
    return {"project_roots": settings.project_roots}


@router.delete("/project-roots")
@limiter.limit(STANDARD)
def remove_project_root(
    request: Request,
    req: RemoveProjectRootRequest,
    settings: Settings = Depends(get_settings),
    tracking=Depends(get_tracking),
    store=Depends(get_store),
):
    """Remove a project root.

    When cleanup=true, also unindexes all files from the expanded directories.
    """
    # Capture expanded dirs before removing so we can clean up
    removed_count = 0
    if req.cleanup:
        resolved_root = str(Path(req.path).resolve())
        all_files = tracking.get_all_files()
        for f in all_files:
            fpath = f["path"]
            if fpath.startswith(resolved_root + "/"):
                store.delete_by_source(fpath)
                tracking.unindex_file(fpath)
                removed_count += 1

    settings.remove_project_root(req.path)
    settings.save()
    return {"project_roots": settings.project_roots, "unindexed_count": removed_count}


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
                "api_key_set": bool(settings.resolve_provider_key(p["name"])),
                "api_key_source": "env" if settings.key_is_from_env(p["name"]) else "yaml",
                "temperature": p.get("temperature"),
                "max_tokens": p.get("max_tokens"),
                "num_ctx": p.get("num_ctx"),
            }
            for p in settings.llm_providers
        ],
        "features": settings.features,
        "mcp": settings.mcp_config,
        "sources": settings.sources,
        "project_roots": settings.project_roots,
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
        "log_level": settings.log_level,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        "num_ctx": settings.llm_num_ctx,
    }


@router.put("/settings/provider")
@limiter.limit(STANDARD)
def save_provider(
    request: Request,
    req: ProviderSettingsRequest,
    settings: Settings = Depends(get_settings),
):
    """Save LLM provider configuration.

    API keys are never written to YAML — they must be provided via
    Docker secrets or environment variables.
    """
    settings.active_provider = req.name
    for p in settings.llm_providers:
        if p.get("name") == req.name:
            p["model"] = req.model
            p["api_base"] = req.api_base
            # Never write api_key to YAML — use secrets/env vars instead
            p.pop("api_key", None)
            break
    settings.save()
    return {"status": "saved"}


@router.put("/settings/llm-params")
@limiter.limit(STANDARD)
def save_llm_params(
    request: Request,
    req: LlmParamsRequest,
    settings: Settings = Depends(get_settings),
):
    """Save LLM generation parameters (temperature, max_tokens, num_ctx)."""
    settings.llm_temperature = req.temperature
    settings.llm_max_tokens = req.max_tokens
    settings.llm_num_ctx = req.num_ctx
    settings.save()
    return {"status": "saved"}


@router.post("/settings/test-connection")
@limiter.limit(LLM)
def test_connection(
    request: Request,
    req: TestConnectionRequest,
    settings: Settings = Depends(get_settings),
):
    """Test LLM provider connection."""
    api_key = req.api_key or settings.resolve_provider_key(req.name)
    result = test_llm_connection(
        req.name,
        req.model,
        req.api_base,
        api_key,
    )
    success = not result.startswith(("Connection failed", "Cannot reach", "No model"))
    return {"result": result, "success": success}


@router.post("/settings/ping-model")
@limiter.limit(LLM)
def ping_model_endpoint(
    request: Request,
    req: TestConnectionRequest,
    settings: Settings = Depends(get_settings),
):
    """Ping a specific model to check availability."""
    api_key = req.api_key or settings.resolve_provider_key(req.name)
    result = ping_model(req.model, req.api_base, api_key)
    success = not result.startswith(("Connection failed", "No model"))
    return {"result": result, "success": success}


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
        api_key = req.api_key or ""
    else:
        active = settings.get_active_llm_config()
        model = active.get("model", "")
        api_base = active.get("api_base", "") or ""
        api_key = active.get("api_key", "") or ""

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
                api_key,
                settings.llm_num_ctx,
            ):
                yield sse(event, data)
        except (RuntimeError, ConnectionError, TimeoutError) as e:
            logger.error("Test prompt error: %s", e)
            yield sse("error", {"message": "LLM request failed. Check server logs for details."})

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


# -- Plugin Settings --

@router.get("/settings/plugins/{plugin_name}")
@limiter.limit(STANDARD)
def get_plugin_settings(
    request: Request,
    plugin_name: str,
    settings: Settings = Depends(get_settings),
):
    """Get configuration for a specific plugin."""
    return {"plugin": plugin_name, "config": settings.get_plugin_config(plugin_name)}


@router.put("/settings/plugins/{plugin_name}")
@limiter.limit(STANDARD)
def update_plugin_settings(
    request: Request,
    plugin_name: str,
    config: dict,
    settings: Settings = Depends(get_settings),
):
    """Update configuration for a specific plugin (shallow merge)."""
    if not all(isinstance(k, str) for k in config):
        raise HTTPException(400, "Plugin config keys must be strings")
    settings.set_plugin_config(plugin_name, config)
    settings.save()
    return {"status": "saved", "plugin": plugin_name, "config": settings.get_plugin_config(plugin_name)}


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
    req: McpToolConfigRequest,
    settings: Settings = Depends(get_settings),
):
    """Update configuration for a specific MCP tool."""
    settings.set_mcp_config(req.tool_name, req.config)
    settings.save()
    return {"status": "saved", "tool_name": req.tool_name}


# -- Logging --

@router.get("/settings/log-level")
@limiter.limit(STANDARD)
def get_log_level(request: Request, settings: Settings = Depends(get_settings)):
    """Get the current logging level."""
    return {"level": settings.log_level}


@router.put("/settings/log-level")
@limiter.limit(STANDARD)
def set_log_level(
    request: Request,
    req: LogLevelRequest,
    settings: Settings = Depends(get_settings),
):
    """Set the logging level (INFO or DEBUG) and persist to config."""
    level = getattr(logging, req.level, logging.INFO)
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


# -- Database Maintenance --

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
            "tracking_path": str(data_dir / "mdkb.db"),
            "chroma_path": str(data_dir / "chromadb"),
            "size_bytes": (
                get_path_size(data_dir / "mdkb.db")
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

    # Trigger reindex in background
    # Note: The actual reindexing will happen via the existing /api/index endpoint
    return {
        "status": "cleared",
        "database": "vectors",
        "message": "Vector database cleared. Use the reindex endpoint to rebuild.",
    }


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
