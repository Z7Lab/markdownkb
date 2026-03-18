"""MCP tool: list named scopes (folder + tag filters)."""

TOOL = {
    "name": "list_scopes",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler() -> dict:
    """List all named scopes.

    Scopes are saved filter presets combining folder paths and tags.
    Use them to narrow retrieval and search to specific parts of the
    knowledge base.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    scopedb = deps.get("scopedb")

    if scopedb is None:
        return {"scopes": [], "error": "ScopeDB not available"}

    scopes = scopedb.list_scopes()
    return {
        "scopes": [
            {
                "id": s["id"],
                "name": s["name"],
                "folders": s["folders"],
                "tags": s["tags"],
            }
            for s in scopes
        ],
        "total": len(scopes),
    }
