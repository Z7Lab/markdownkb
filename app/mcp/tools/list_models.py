"""MCP tool: list available LLM models."""

from app.config import Settings

TOOL = {
    "name": "list_models",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler() -> dict:
    """List configured LLM providers and the active model.

    Returns the active provider/model and all configured providers
    with their connection status.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    settings: Settings = deps["settings"]

    active_cfg = settings.get_active_llm_config()
    providers = []
    for p in settings.llm_providers:
        providers.append({
            "name": p.get("name", ""),
            "model": p.get("model", ""),
            "api_base": p.get("api_base", ""),
            "has_key": bool(p.get("api_key")),
        })

    return {
        "active_provider": settings.active_provider,
        "active_model": active_cfg.get("model", "") if active_cfg else "",
        "providers": providers,
    }
