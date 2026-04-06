"""MCP tool: re-index a single markdown file."""

from pathlib import Path

from app.config import Settings
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

TOOL = {
    "name": "index_file",
    "feature_flag": None,
    "write": True,
}

_mcp = None  # Injected by register_tools()


def handler(path: str) -> dict:
    """Re-index a single markdown file, updating the vector store."""
    from app.ingestion.watcher import reindex_file

    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    settings: Settings = deps["settings"]
    store: VectorStore = deps["store"]
    tracking: TrackingDB = deps["tracking"]

    resolved = str(Path(path).resolve())

    if not resolved.endswith(".md"):
        raise ValueError("Only .md files can be indexed")

    in_source = any(
        resolved == str(Path(s).resolve())
        or resolved.startswith(str(Path(s).resolve()) + "/")
        for s in settings.sources
    )
    if not in_source:
        raise ValueError("File is not within a configured source directory")

    kgdb = deps.get("kgdb")
    reindex_file(resolved, settings, store, tracking, kgdb=kgdb)

    record = tracking.get_file(resolved)
    return {
        "status": record.get("status", "unknown") if record else "not_found",
        "chunk_count": record.get("chunk_count", 0) if record else 0,
        "path": resolved,
    }
