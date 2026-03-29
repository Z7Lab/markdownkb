"""MCP tool: RAG chat scoped to a temporary bucket."""

TOOL = {
    "name": "bucket_chat",
    "feature_flag": None,
    "requires_plugin": "buckets",
}

_mcp = None  # Injected by register_tools()


def handler(bucket: str, message: str) -> dict:
    """Ask a question and get an answer grounded in a specific bucket's documents.

    Uses RAG to find relevant documents within the bucket and generate
    a contextual response via the configured LLM.

    Args:
        bucket: Bucket name or ID.
        message: Question or message to answer.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    svc = deps["bucket_service"]
    settings = deps["settings"]
    return svc.chat(bucket, message, settings)
