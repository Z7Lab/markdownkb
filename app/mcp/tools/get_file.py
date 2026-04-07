"""MCP tool: read content of a file within configured sources."""

from pathlib import Path

from app.config import Settings
from app.storage.trackingdb import TrackingDB

TOOL = {
    "name": "get_file",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler(path: str, page: int | None = None, page_size: int = 5000) -> dict:
    """Read the full content of a file by its path.

    Use this to read complete documents — for example, after ``search``
    or ``chat`` returns a source path you want to read in full. The file
    must be within a configured source directory.

    Supports pagination for large files via ``page`` and ``page_size``
    (measured in lines).  When ``page`` is omitted the full content is
    returned.  Page numbering starts at 1.
    """
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

    if not Path(resolved).exists():
        raise ValueError(f"File not found: {path}")

    try:
        content = Path(resolved).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ValueError(f"Cannot read file: {exc}") from exc

    result: dict = {"path": resolved}

    # Include index metadata when available
    record = tracking.get_file(resolved)
    if record:
        result["status"] = record.get("status", "unknown")
        result["chunk_count"] = record.get("chunk_count", 0)
    else:
        result["status"] = "not_indexed"
        result["chunk_count"] = 0

    if page is not None:
        if page < 1:
            raise ValueError("Page number must be 1 or greater")
        if page_size < 100 or page_size > 50000:
            raise ValueError("page_size must be between 100 and 50000")
        lines = content.splitlines(keepends=True)
        total_lines = len(lines)
        total_pages = max(1, (total_lines + page_size - 1) // page_size)
        if page > total_pages:
            raise ValueError(
                f"Page {page} not found (file has {total_pages} page(s))"
            )
        start = (page - 1) * page_size
        end = start + page_size
        result["content"] = "".join(lines[start:end])
        result["page"] = page
        result["total_pages"] = total_pages
        result["total_lines"] = total_lines
        result["page_size"] = page_size
    else:
        result["content"] = content

    return result
