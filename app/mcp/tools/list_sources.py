"""MCP tool: list configured source directories."""

from app.config import Settings

TOOL = {
    "name": "list_sources",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler() -> dict:
    """List all configured source directories being watched."""
    ctx = _mcp.get_context()
    settings: Settings = ctx.request_context.lifespan_context["settings"]
    return {"sources": settings.sources}
