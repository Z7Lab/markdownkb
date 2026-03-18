"""MCP tool: server health status."""

from app.config import Settings
from app.storage.vectorstore import VectorStore

TOOL = {
    "name": "health",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler() -> dict:
    """Check server health and return basic status.

    Returns chunk count, active LLM provider, and configured sources.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    store: VectorStore = deps["store"]
    settings: Settings = deps["settings"]

    active_cfg = settings.get_active_llm_config()
    return {
        "status": "ok",
        "chunks": store.count,
        "provider": settings.active_provider,
        "model": active_cfg.get("model", "") if active_cfg else "",
        "sources": len(settings.sources),
    }
