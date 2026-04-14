"""MCP tool: ingest a source document into a managed wiki.

Thin wrapper over the same service function the HTTP route calls. The
``wiki`` argument is a managed-wiki name; resolve via WikiDB to a path
and delegate to the plugin's ingest service.
"""

from app.config import Settings
from app.rag.retriever import Retriever
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
    wiki: str,
    force: bool = False,
) -> dict:
    """Read a source document, synthesize a summary page via the configured
    LLM, and write it into a managed wiki. Updates index.md and log.md.
    Existing related pages from the target wiki are passed as context so
    the new summary can note overlaps.

    Args:
        source_path: Absolute path to a readable file on disk. Does not
                     need to be a configured source. Content is truncated
                     to 8000 characters before the LLM call.
        wiki: Managed wiki name. Use ``wiki_compile_list`` to see what's
              available; ``wiki_compile_create`` to make one.
        force: Overwrite an existing summary page for the same source
               (default False).

    Returns:
        Dict with status, source_path, target_source, pages_written,
        existing_pages_used, summary_preview, summary_chars, wiki.
    """
    ctx = _mcp.get_context()
    settings: Settings = ctx.request_context.lifespan_context["settings"]
    retriever: Retriever = ctx.request_context.lifespan_context["retriever"]
    wikidb = ctx.request_context.lifespan_context.get("wikidb")
    if wikidb is None:
        raise ValueError("wiki_compile plugin is disabled")

    record = wikidb.get_by_name(wiki)
    if not record:
        raise ValueError(f"Wiki not found: {wiki}")

    try:
        result = ingest(
            source_path=source_path,
            target_source=record["path"],
            settings=settings,
            retriever=retriever,
            force=force,
        )
        result["wiki"] = wiki
        return result
    except WikiCompileError as e:
        raise ValueError(str(e)) from e
