"""MCP tool: save a markdown file to the knowledge base."""

import logging
import re
from pathlib import Path

from app.config import Settings

TOOL = {
    "name": "save_file",
    "feature_flag": "save_document",
    "write": True,
}

_mcp = None  # Injected by register_tools()

logger = logging.getLogger(__name__)

# Characters not allowed in filenames
_UNSAFE_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')


def handler(
    path: str,
    content: str,
    source: str = "",
    overwrite: bool = False,
) -> dict:
    """Save a markdown document to a watched source directory.

    The file is written to disk and automatically indexed by the file
    watcher.  Use this to store captures, notes, or any markdown content
    in the knowledge base.

    Args:
        path: Relative path within the source directory (e.g.
              'captures/2026-03-15-meeting.md').  Must end with .md.
        content: Markdown content to write.
        source: Source directory to write into (must be a configured
                source).  Defaults to the first configured source.
        overwrite: Allow overwriting an existing file (default False).
    """
    ctx = _mcp.get_context()
    settings: Settings = ctx.request_context.lifespan_context["settings"]

    # -- Validate path --------------------------------------------------------
    normalized = Path(path)
    if normalized.is_absolute():
        raise ValueError("Path must be relative")
    for part in normalized.parts:
        if part == "..":
            raise ValueError("Path traversal ('..') is not allowed")
    if _UNSAFE_CHARS.search(path):
        raise ValueError("Path contains invalid characters")
    if not path.endswith(".md"):
        raise ValueError("Only .md files are supported")

    relative = str(normalized)

    # -- Resolve target source directory --------------------------------------
    sources = settings.sources
    if not sources:
        raise ValueError("No source directories configured")

    if source:
        resolved_source = str(Path(source).resolve())
        if resolved_source not in [str(Path(s).resolve()) for s in sources]:
            raise ValueError(f"'{source}' is not a configured source directory")
        target_dir = Path(resolved_source)
    else:
        target_dir = Path(sources[0])

    full_path = target_dir / relative

    # -- Guard against accidental overwrite -----------------------------------
    if full_path.exists() and not overwrite:
        raise ValueError(
            f"File already exists: {relative}. Set overwrite=true to replace."
        )

    # -- Write ----------------------------------------------------------------
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Failed to write file: {exc}") from exc

    logger.info("Document saved via MCP: %s", full_path)
    return {
        "status": "created" if not overwrite else "written",
        "path": str(full_path),
        "relative_path": relative,
        "source": str(target_dir),
    }
