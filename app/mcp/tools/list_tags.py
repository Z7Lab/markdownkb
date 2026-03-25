"""MCP tool: list tags and their file counts."""

TOOL = {
    "name": "list_tags",
    "feature_flag": None,
    "requires_plugin": "tags",
}

_mcp = None  # Injected by register_tools()


def handler(file_path: str = "") -> dict:
    """List tags in the knowledge base.

    With no arguments, returns all tags with file counts.
    With a file_path, returns tags for that specific file.

    Args:
        file_path: Optional file path to get tags for a specific file.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    tagdb = deps.get("tagdb")

    if tagdb is None:
        return {"tags": [], "error": "TagDB not available"}

    if file_path:
        tags_str = tagdb.get_tags(file_path)
        tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
        return {"file": file_path, "tags": tags}

    # All tags with counts
    all_tags = tagdb.get_all_tags_with_counts()
    return {
        "tags": [
            {"name": t["tag"], "count": t["count"]}
            for t in all_tags
        ],
        "total": len(all_tags),
    }
