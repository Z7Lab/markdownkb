"""MCP tool: delete a markdown file from the knowledge base."""

import logging
from pathlib import Path

from app.config import Settings
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

TOOL = {
    "name": "delete_file",
    "feature_flag": "save_document",
    "write": True,
}

_mcp = None  # Injected by register_tools()

logger = logging.getLogger(__name__)


def handler(path: str) -> dict:
    """Delete a markdown file from a watched source directory.

    Removes the file from disk, the vector store, and the tracking
    database. The file must be within a configured source directory.

    Args:
        path: Absolute or relative path to the file. Relative paths
              are resolved against the first configured source.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    settings: Settings = deps["settings"]
    store: VectorStore = deps["store"]
    tracking: TrackingDB = deps["tracking"]

    resolved = str(Path(path).resolve())

    if not resolved.endswith(".md"):
        raise ValueError("Only .md files can be deleted")

    # Verify file is within a configured source directory
    in_source = any(
        resolved == str(Path(s).resolve())
        or resolved.startswith(str(Path(s).resolve()) + "/")
        for s in settings.sources
    )
    if not in_source:
        raise ValueError("File is not within a configured source directory")

    # Check writable flag on the matching source
    if not settings.is_source_writable(resolved):
        # Check parent directories too
        for s in settings.sources:
            s_resolved = str(Path(s).resolve())
            if resolved.startswith(s_resolved + "/") and not settings.is_source_writable(s_resolved):
                raise ValueError(f"Source '{s_resolved}' is read-only (writable: false in settings)")

    file_path = Path(resolved)
    if not file_path.exists():
        raise ValueError(f"File not found: {resolved}")

    # Remove from disk
    try:
        file_path.unlink()
    except OSError as exc:
        raise ValueError(f"Failed to delete file: {exc}") from exc

    # Remove from vector store and tracking
    store.delete_by_source(resolved)
    tracking.remove_file(resolved)

    # Notify tag system if available
    from app.domains.tag_registry import notify_file_deleted
    notify_file_deleted(resolved)

    logger.info("Document deleted via MCP: %s", resolved)
    return {"status": "deleted", "path": resolved}
