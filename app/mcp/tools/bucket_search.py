"""MCP tool: search within a temporary bucket."""

TOOL = {
    "name": "bucket_search",
    "feature_flag": None,
    "requires_plugin": "buckets",
}

_mcp = None  # Injected by register_tools()


def handler(bucket: str, query: str, top_k: int = 5) -> dict:
    """Search within a temporary bucket using vector similarity.

    Returns results in the same format as the retrieve tool.

    Args:
        bucket: Bucket name or ID.
        query: Search query string.
        top_k: Maximum number of results to return (default 5).
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    svc = deps["bucket_service"]
    settings = deps["settings"]
    return svc.search(bucket, query, top_k, settings)
