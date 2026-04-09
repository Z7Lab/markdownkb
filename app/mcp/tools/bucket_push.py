"""MCP tool: push markdown documents into a bucket by content."""

import json
import logging

TOOL = {
    "name": "bucket_push",
    "requires_plugin": "buckets",
    "write": True,
    "bucket_write": True,
}

_mcp = None  # Injected by register_tools()

logger = logging.getLogger(__name__)


def handler(
    bucket: str,
    documents: str,
) -> dict:
    """Push markdown documents into a bucket by content — no filesystem access needed.

    Use this when you're on a different machine from MarkdownKB and can't
    provide a local directory path.  Each document is embedded and indexed
    into the bucket immediately.

    Args:
        bucket: Bucket ID or name.
        documents: JSON array of objects, each with "name" (virtual filename
                   ending in .md) and "content" (raw markdown text).
                   Example: [{"name": "notes.md", "content": "# My Notes\\n\\nContent..."}]
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    bucket_service = deps.get("bucket_service")
    if not bucket_service:
        raise ValueError("Buckets plugin not available")

    try:
        docs = json.loads(documents)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in documents parameter: {e}") from e

    if not isinstance(docs, list):
        raise ValueError("documents must be a JSON array")

    return bucket_service.push_documents(bucket, docs)
