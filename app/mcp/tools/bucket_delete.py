"""MCP tool: delete a temporary bucket."""

TOOL = {
    "name": "bucket_delete",
    "feature_flag": None,
    "requires_plugin": "buckets",
    "write": True,
}

_mcp = None  # Injected by register_tools()


def handler(bucket: str) -> dict:
    """Delete a temporary bucket and its vector data.

    Args:
        bucket: Bucket name or ID.

    Returns:
        Dict with deleted=True, id, and name of the deleted bucket.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    svc = deps["bucket_service"]
    return svc.delete(bucket)
