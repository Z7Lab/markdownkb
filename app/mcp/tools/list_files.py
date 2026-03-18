"""MCP tool: list all indexed files."""

from app.storage.trackingdb import TrackingDB

TOOL = {
    "name": "list_files",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler(status: str = "") -> dict:
    """List all indexed documents.

    Optionally filter by status: 'complete', 'pending', 'error'.
    """
    ctx = _mcp.get_context()
    tracking: TrackingDB = ctx.request_context.lifespan_context["tracking"]

    files = tracking.get_all_files()
    if status:
        files = [f for f in files if f.get("status") == status]

    return {
        "documents": [
            {
                "path": f["path"],
                "status": f.get("status", "unknown"),
                "chunk_count": f.get("chunk_count", 0),
            }
            for f in files
        ],
        "total": len(files),
    }
