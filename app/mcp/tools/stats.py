"""MCP tool: knowledge base statistics."""

from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

TOOL = {
    "name": "stats",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler() -> dict:
    """Get knowledge base statistics — document counts, index status."""
    ctx = _mcp.get_context()
    tracking: TrackingDB = ctx.request_context.lifespan_context["tracking"]
    store: VectorStore = ctx.request_context.lifespan_context["store"]

    return {
        **tracking.get_stats(),
        "vector_count": store.count,
    }
