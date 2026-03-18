"""MCP tool: read full content of an indexed file."""

from pathlib import Path

from app.config import Settings
from app.storage.trackingdb import TrackingDB

TOOL = {
    "name": "get_file",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler(path: str) -> dict:
    """Read the full content of an indexed markdown file by its path."""
    ctx = _mcp.get_context()
    settings: Settings = ctx.request_context.lifespan_context["settings"]
    tracking: TrackingDB = ctx.request_context.lifespan_context["tracking"]

    resolved = str(Path(path).resolve())

    # Verify the file belongs to a configured source (trailing / prevents
    # sibling-dir bypass, e.g. /docs matching /docs-private)
    in_source = any(
        resolved.startswith(str(Path(s).resolve()) + "/")
        for s in settings.sources
    )
    if not in_source:
        raise ValueError("Path is not within a configured source directory")

    record = tracking.get_file(resolved)
    if not record:
        raise ValueError("File is not indexed")

    try:
        content = Path(resolved).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read file: {exc}") from exc

    return {
        "path": resolved,
        "content": content,
        "status": record.get("status", "unknown"),
        "chunk_count": record.get("chunk_count", 0),
    }
