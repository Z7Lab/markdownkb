"""MCP tool: add documents to an existing bucket."""

TOOL = {
    "name": "bucket_add",
    "feature_flag": None,
    "requires_plugin": "buckets",
    "write": True,
}

_mcp = None  # Injected by register_tools()


def handler(bucket: str, sources: list[dict]) -> dict:
    """Add documents to an existing bucket without recreating it.

    Parses, chunks, and embeds new files into the bucket.  Files already
    present in the bucket are skipped automatically.

    Args:
        bucket: Bucket name or ID.
        sources: List of source descriptors.  Each must have a "path" key
                 (absolute path to a file or directory) and an optional
                 "glob" key (default "**/*.md").
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    svc = deps["bucket_service"]
    return svc.add_documents(bucket, sources)
