"""MCP tool: list writable sources that are valid wiki-compile targets.

Companion to ``wiki_compile_ingest`` — lets an agent discover which
directories it may write into before attempting an ingest.
"""

from app.config import Settings

TOOL = {
    "name": "wiki_compile_targets",
    "feature_flag": None,
    "requires_plugin": "wiki_compile",
    "write": False,
}

_mcp = None  # Injected by register_tools()


def handler() -> dict:
    """List writable sources that are valid ingest targets for wiki_compile.

    The ``wiki_compile_ingest`` tool's ``target_source`` argument must
    match one of the paths returned here; anything else is rejected.

    Returns:
        Dict with ``targets`` — a list of absolute paths.
    """
    ctx = _mcp.get_context()
    settings: Settings = ctx.request_context.lifespan_context["settings"]
    return {"targets": settings.writable_sources}
