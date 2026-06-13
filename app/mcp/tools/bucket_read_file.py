"""MCP tool: read a file's full content from a bucket."""

import logging

from app.ingestion.reconstruct import reconstruct_chunks

TOOL = {
    "name": "bucket_read_file",
    "requires_plugin": "buckets",
}

_mcp = None  # Injected by register_tools()

logger = logging.getLogger(__name__)


def handler(bucket: str, path: str) -> dict:
    """Read a file's full content from a bucket.

    Reconstructs the document from stored chunks. Works for both
    filesystem-sourced and pushed (virtual) documents.

    Args:
        bucket: Bucket ID or name.
        path: The source_path of the file (from bucket_list_files results).
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    bucket_service = deps.get("bucket_service")
    if not bucket_service:
        raise ValueError("Buckets plugin not available")

    record = bucket_service.db.resolve(bucket)
    if not record:
        raise ValueError(f"Bucket not found: {bucket}")

    store = bucket_service.get_store(record["id"])
    result = store._collection.get(
        where={"source_path": path},
        include=["documents", "metadatas"],
    )
    if not result["ids"]:
        raise ValueError(f"File not found in bucket: {path}")

    chunks = sorted(
        zip(result["documents"], result["metadatas"]),
        key=lambda x: x[1].get("chunk_index", 0),
    )

    title = chunks[0][1].get("title", "") if chunks else ""

    return {
        "path": path,
        "title": title,
        "content": reconstruct_chunks([doc for doc, _meta in chunks]),
        "chunk_count": len(chunks),
    }
