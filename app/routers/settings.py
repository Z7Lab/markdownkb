"""Core settings endpoints: GET /settings, features, prompts, retrieval, plugins, MCP."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import Settings
from app.deps import get_settings
from app.ratelimit import STANDARD, limiter
from app.schemas import (
    FeatureToggleRequest,
    McpToolConfigRequest,
    RetrievalSettingsRequest,
    SearchSummaryPromptRequest,
    SystemPromptRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["settings"])


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


@router.put("/settings/features")
@limiter.limit(STANDARD)
def toggle_feature(
    request: Request,
    req: FeatureToggleRequest,
    settings: Settings = Depends(get_settings),
):
    """Toggle a feature flag on or off."""
    settings.set_feature(req.name, req.enabled)
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
