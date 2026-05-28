"""Core settings endpoints: GET /settings, features, prompts, retrieval, plugins, MCP."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import Settings
from app.deps import get_presetsdb, get_settings, get_versioning_manager
from app.services.settings_service import build_settings_response
from app.storage.presetsdb import PresetsDB
from app.ratelimit import STANDARD, limiter
from app.schemas.mcp import McpToolConfigRequest
from app.schemas.settings import CreatePresetRequest, FeatureToggleRequest, PluginConfigRequest, RetrievalSettingsRequest, SearchSummaryPromptRequest, SystemPromptRequest, UpdatePresetRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["settings"])


@router.get("/settings")
@limiter.limit(STANDARD)
def get_settings_endpoint(request: Request, settings: Settings = Depends(get_settings)):
    """Get all application settings."""
    return build_settings_response(settings)



_KNOWN_CORE_FLAGS = frozenset({
    "file_watcher", "rate_limiting",
    "deep_research", "agent_skills",
    "versioning", "update_check",
})

# Active MCP toggle flags accepted by this API endpoint.
# Distinct from the removed _MCP_FLAGS dict in app/config/_migrations.py,
# which mapped legacy feature-flag names for the one-time migration path.
_KNOWN_MCP_FLAGS = frozenset({
    "read_only", "allow_bucket_writes", "save_document", "track_history",
})


@router.put("/settings/core")
@limiter.limit(STANDARD)
def toggle_core(
    request: Request,
    req: FeatureToggleRequest,
    settings: Settings = Depends(get_settings),
    versioning_manager=Depends(get_versioning_manager),
):
    """Toggle a core behaviour flag."""
    if req.name not in _KNOWN_CORE_FLAGS:
        raise HTTPException(400, f"Unknown core flag: {req.name}")
    settings.set_core(req.name, req.enabled)
    settings.save()
    # Side-effect: lazy-init the versioning manager so the toggle takes
    # effect without a restart. Other flags are runtime-checked and need
    # no side-effects here.
    if req.name == "versioning" and req.enabled and versioning_manager is None:
        try:
            from pathlib import Path
            from app.versioning import GitManager
            request.app.state.versioning_manager = GitManager(
                Path(settings.versioning_root)
            )
        except Exception:
            logger.warning("Could not init GitManager on toggle", exc_info=True)
    return {"status": "saved"}


@router.put("/settings/mcp-flags")
@limiter.limit(STANDARD)
def toggle_mcp_flag(
    request: Request,
    req: FeatureToggleRequest,
    settings: Settings = Depends(get_settings),
):
    """Toggle an MCP tool enable flag."""
    if req.name not in _KNOWN_MCP_FLAGS:
        raise HTTPException(400, f"Unknown MCP flag: {req.name}")
    settings.set_mcp_enabled(req.name, req.enabled)
    settings.save()
    return {"status": "saved"}


@router.put("/settings/plugins/{plugin_name}/enabled")
@limiter.limit(STANDARD)
def toggle_plugin(
    request: Request,
    plugin_name: str,
    req: FeatureToggleRequest,
    settings: Settings = Depends(get_settings),
):
    """Toggle a plugin's enabled state."""
    settings.set_plugin_enabled(plugin_name, req.enabled)
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

def _known_plugin_names() -> set[str]:
    """Return the set of plugins known to the registry (builtin + external)."""
    from app.plugins import discover_plugins
    return {p["name"] for p in discover_plugins()}


def _require_known_plugin(plugin_name: str) -> None:
    if plugin_name not in _known_plugin_names():
        raise HTTPException(status_code=404, detail="Unknown plugin")


@router.get("/settings/plugins/{plugin_name}")
@limiter.limit(STANDARD)
def get_plugin_settings(
    request: Request,
    plugin_name: str,
    settings: Settings = Depends(get_settings),
):
    """Get configuration for a specific plugin."""
    _require_known_plugin(plugin_name)
    return {"plugin": plugin_name, "config": settings.get_plugin_config(plugin_name)}


@router.put("/settings/plugins/{plugin_name}")
@limiter.limit(STANDARD)
def update_plugin_settings(
    request: Request,
    plugin_name: str,
    req: PluginConfigRequest,
    settings: Settings = Depends(get_settings),
):
    """Update configuration for a specific plugin (shallow merge)."""
    _require_known_plugin(plugin_name)
    settings.set_plugin_config(plugin_name, req.config)
    settings.save()
    return {"status": "saved", "plugin": plugin_name, "config": settings.get_plugin_config(plugin_name)}


# -- Dashboard Widget Settings --

@router.put("/settings/dashboard-widgets/{widget_name}")
@limiter.limit(STANDARD)
def toggle_dashboard_widget(
    request: Request,
    widget_name: str,
    req: FeatureToggleRequest,
    settings: Settings = Depends(get_settings),
):
    """Toggle dashboard widget visibility."""
    settings.set_dashboard_widget_enabled(widget_name, req.enabled)
    settings.save()
    return {"status": "saved", "widget": widget_name, "enabled": req.enabled}


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


# -- Retrieval Presets --

@router.get("/settings/presets")
@limiter.limit(STANDARD)
def list_presets(
    request: Request,
    presetsdb: PresetsDB = Depends(get_presetsdb),
):
    """List all retrieval presets."""
    presets = presetsdb.list_presets()
    return {"presets": presets, "total": len(presets)}


@router.post("/settings/presets", status_code=201)
@limiter.limit(STANDARD)
def create_preset(
    request: Request,
    body: CreatePresetRequest,
    presetsdb: PresetsDB = Depends(get_presetsdb),
    settings: Settings = Depends(get_settings),
):
    """Create a retrieval preset.

    Body: {"name": "...", "settings": {...}} or {"name": "..."} to snapshot current.
    """
    name = body.name.strip()
    preset_settings = body.settings
    if not preset_settings:
        # Snapshot current retrieval settings
        preset_settings = {
            "top_k": settings.top_k,
            "score_threshold": settings.score_threshold,
            "hybrid_search": settings.hybrid_search,
            "bm25_weight": settings.bm25_weight,
        }
    try:
        preset_id = presetsdb.create(name, preset_settings)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"id": preset_id, "status": "created"}


@router.put("/settings/presets/{preset_id}")
@limiter.limit(STANDARD)
def update_preset(
    request: Request,
    preset_id: str,
    body: UpdatePresetRequest,
    presetsdb: PresetsDB = Depends(get_presetsdb),
):
    """Update a preset's name and/or settings."""
    try:
        found = presetsdb.update(
            preset_id,
            name=body.name,
            settings=body.settings,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not found:
        raise HTTPException(404, "Preset not found")
    return {"status": "updated"}


@router.delete("/settings/presets/{preset_id}")
@limiter.limit(STANDARD)
def delete_preset(
    request: Request,
    preset_id: str,
    presetsdb: PresetsDB = Depends(get_presetsdb),
):
    """Delete a retrieval preset."""
    if not presetsdb.delete(preset_id):
        raise HTTPException(404, "Preset not found")
    return {"status": "deleted"}


@router.post("/settings/presets/{preset_id}/load")
@limiter.limit(STANDARD)
def load_preset(
    request: Request,
    preset_id: str,
    presetsdb: PresetsDB = Depends(get_presetsdb),
    settings: Settings = Depends(get_settings),
):
    """Apply a preset's settings to the active retrieval configuration."""
    preset = presetsdb.get(preset_id)
    if not preset:
        raise HTTPException(404, "Preset not found")
    s = preset["settings"]
    if "top_k" in s:
        settings.top_k = s["top_k"]
    if "score_threshold" in s:
        settings.score_threshold = s["score_threshold"]
    if "hybrid_search" in s:
        settings.hybrid_search = s["hybrid_search"]
    if "bm25_weight" in s:
        settings.bm25_weight = s["bm25_weight"]
    settings.save()
    return {"status": "loaded", "name": preset["name"], "settings": s}


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
