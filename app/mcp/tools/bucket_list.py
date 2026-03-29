"""MCP tool: list all temporary buckets."""

TOOL = {
    "name": "bucket_list",
    "feature_flag": None,
    "requires_plugin": "buckets",
}

_mcp = None  # Injected by register_tools()


def handler() -> dict:
    """List all temporary buckets with their metadata.

    Returns:
        Dict with "buckets" key containing a list of bucket records,
        each with id, name, file_count, chunk_count, created_at,
        and expires_at.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    svc = deps["bucket_service"]
    return {"buckets": svc.db.list_all()}
