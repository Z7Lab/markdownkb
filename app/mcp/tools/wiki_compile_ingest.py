"""MCP tool: ingest a source document into a wiki target directory.

Thin wrapper over ``app.plugins.wiki_compile.service.ingest`` — the HTTP
route and this MCP tool both call the same service function so the
plugin logic stays in one place. Write-protection (target must be a
writable source) is enforced inside the service.
"""

from app.config import Settings
from app.plugins.wiki_compile.service import WikiCompileError, ingest

TOOL = {
    "name": "wiki_compile_ingest",
    "feature_flag": None,
    "requires_plugin": "wiki_compile",
    "write": True,
}

_mcp = None  # Injected by register_tools()


def handler(
    source_path: str,
    target_source: str,
    force: bool = False,
) -> dict:
    """Read a source document, synthesize a summary page via the configured
    LLM, and write it into a writable source directory. Updates index.md
    and appends log.md.

    Args:
        source_path: Absolute path to a readable file on disk. Does not
                     need to be a configured source. Content is
                     truncated to 8000 characters before the LLM call.
        target_source: Configured writable source directory (must have
                       ``writable: true``). Call ``list_wiki_compile_targets``
                       or the GET /api/wiki-compile/targets endpoint to
                       get the list of valid targets.
        force: Overwrite an existing summary page for the same source
               (default False).

    Returns:
        Dict with status, source_path, target_source, pages_written
        (relative paths to the files created/updated), summary_preview
        (first 300 chars), and summary_chars.
    """
    ctx = _mcp.get_context()
    settings: Settings = ctx.request_context.lifespan_context["settings"]
    try:
        return ingest(
            source_path=source_path,
            target_source=target_source,
            settings=settings,
            force=force,
        )
    except WikiCompileError as e:
        raise ValueError(str(e)) from e
