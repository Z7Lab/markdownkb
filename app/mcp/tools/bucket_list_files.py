"""MCP tool: list files in a temporary bucket."""

from pathlib import Path

TOOL = {
    "name": "bucket_list_files",
    "feature_flag": None,
    "requires_plugin": "buckets",
}

_mcp = None  # Injected by register_tools()


def handler(bucket: str) -> dict:
    """List all files indexed in a bucket.

    Returns the file paths and chunk counts for every document in the
    bucket.  Use this to understand what a bucket contains before
    searching or chatting with it.

    Args:
        bucket: Bucket name or ID.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    svc = deps["bucket_service"]

    record = svc.db.resolve(bucket)
    if not record:
        raise ValueError(f"Bucket not found: {bucket}")

    store = svc.get_store(record["id"])
    metadatas = store.get_all_metadatas()

    # Group by source_path and count chunks per file
    files: dict[str, int] = {}
    for meta in metadatas:
        path = meta.get("source_path", "")
        if path:
            files[path] = files.get(path, 0) + 1

    return {
        "bucket_id": record["id"],
        "bucket_name": record["name"],
        "files": [
            {
                "path": path,
                "name": Path(path).name,
                "chunk_count": count,
            }
            for path, count in sorted(files.items())
        ],
        "total_files": len(files),
        "total_chunks": len(metadatas),
    }
