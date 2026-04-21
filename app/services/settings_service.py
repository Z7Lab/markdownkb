"""Settings response construction — extracted from the GET /settings route.

Keeps the HTTP handler in ``app/routers/settings.py`` thin: the handler
delegates to :func:`build_settings_response`, which assembles the full
settings view without touching FastAPI request objects.
"""

from __future__ import annotations

from app.config import Settings
from app.plugins import get_registry


def _providers_view(settings: Settings) -> list[dict]:
    """Project the configured LLM providers into the API response shape."""
    return [
        {
            "name": p["name"],
            "model": p.get("model", ""),
            "api_base": p.get("api_base", ""),
            "api_key_set": bool(settings.resolve_provider_key(p["name"])),
            "api_key_source": "env" if settings.key_is_from_env(p["name"]) else "yaml",
            "temperature": p.get("temperature"),
            "max_tokens": p.get("max_tokens"),
            "num_ctx": p.get("extra_body", {}).get("num_ctx", p.get("num_ctx")),
        }
        for p in settings.llm_providers
    ]


def _plugins_enabled_view(settings: Settings) -> dict[str, bool]:
    """Return {plugin_name: enabled} based on raw YAML plugins section."""
    return {
        name: cfg.get("enabled", False)
        for name, cfg in settings.raw.get("plugins", {}).items()
    }


def _plugin_manifests_view() -> dict[str, dict]:
    """Return {plugin_name: {name, feature_flag, manifest, enabled}} from the registry."""
    return {
        entry["name"]: {
            "name": entry["name"],
            "feature_flag": entry.get("feature_flag"),
            "manifest": entry.get("manifest") or {},
            "enabled": entry.get("enabled", False),
        }
        for entry in get_registry()
    }


def build_settings_response(settings: Settings) -> dict:
    """Return the full GET /settings response body."""
    active_cfg = settings.get_active_llm_config()
    return {
        "active_provider": settings.active_provider,
        "providers": _providers_view(settings),
        "core": settings.core_features,
        "mcp_flags": settings.mcp_features,
        "plugins_enabled": _plugins_enabled_view(settings),
        "mcp": settings.mcp_config,
        "sources": settings.sources,
        "source_configs": settings.source_configs,
        "project_roots": settings.project_roots,
        "global_ignore": settings.global_ignore,
        "versioning_root": settings.versioning_root,
        "active_model": active_cfg.get("model", ""),
        "active_api_base": active_cfg.get("api_base", ""),
        "system_prompt": settings.system_prompt,
        "default_system_prompt": settings.default_system_prompt,
        "search_summary_prompt": settings.search_summary_prompt,
        "default_search_summary_prompt": settings.default_search_summary_prompt,
        "embedding_model": settings.embedding_model,
        "embedding_provider": settings.embedding_provider,
        "embedding_remote_config": settings.embedding_remote_config,
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
        "plugin_manifests": _plugin_manifests_view(),
        "dashboard_widgets": settings.dashboard_widgets,
    }
