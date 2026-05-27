"""MCP tool: list chat threads."""

TOOL = {
    "name": "list_threads",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler(limit: int = 20) -> dict:
    """List recent chat threads from the knowledge base.

    Args:
        limit: Maximum number of threads to return (default 20).
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    chatdb = deps.get("chatdb")

    if chatdb is None:
        return {"error": "Chat history not available"}

    threads = chatdb.list_threads(limit=limit)
    return {
        "threads": [
            {
                "id": t["id"],
                "title": t["title"],
                "created_at": t["created_at"],
                "updated_at": t["updated_at"],
            }
            for t in threads
        ],
        "total": len(threads),
    }
