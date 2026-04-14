"""MCP tool: list managed wikis.

Agents should call this to discover what wikis are available before
invoking ``wiki_compile_ingest`` with a wiki name.
"""

TOOL = {
    "name": "wiki_compile_list",
    "feature_flag": None,
    "requires_plugin": "wiki_compile",
    "write": False,
}

_mcp = None  # Injected by register_tools()


def handler() -> dict:
    """List all managed wikis — name, path, page count, last ingest date.

    Returns:
        Dict with ``wikis`` — a list of wiki records. Each record has
        ``name``, ``path``, ``page_count``, ``last_ingest_at``,
        ``created_at``, and an internal ``id``.
    """
    ctx = _mcp.get_context()
    wikidb = ctx.request_context.lifespan_context.get("wikidb")
    if wikidb is None:
        return {"wikis": []}
    return {"wikis": wikidb.list_all()}
