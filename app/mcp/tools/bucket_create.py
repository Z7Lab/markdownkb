"""MCP tool: create a temporary document bucket."""

TOOL = {
    "name": "bucket_create",
    "feature_flag": None,
    "requires_plugin": "buckets",
    "write": True,
}

_mcp = None  # Injected by register_tools()


def handler(
    name: str,
    sources: list[dict],
    expires_in: int | None = None,
) -> dict:
    """Create a temporary bucket by ingesting documents from source paths.

    Each bucket gets its own vector store collection for isolated search.

    Args:
        name: Display name for the bucket (must be unique).
        sources: List of source descriptors. Each must have a "path" key
                 (absolute path to a file or directory) and an optional
                 "glob" key (default "**/*.md").
        expires_in: Optional auto-delete after this many seconds.

    Returns:
        Bucket metadata including id, name, file_count, chunk_count,
        created_at, and expires_at.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    svc = deps["bucket_service"]
    return svc.create(name, sources, expires_in)
