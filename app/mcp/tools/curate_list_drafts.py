"""MCP tool: list curate drafts (the curation queue)."""

from app.plugins.curate.curatedb import CurateDB

TOOL = {
    "name": "curate_list_drafts",
    "feature_flag": None,
    "requires_plugin": "curate",
    "write": False,
}

_mcp = None  # Injected by register_tools()


def handler(status: str = "") -> dict:
    """List curate drafts, optionally filtered by status.

    Args:
        status: Filter by lifecycle status — ``draft`` (open for review),
                ``graduated``, or ``rejected``. Empty returns all.

    Returns:
        Dict with ``drafts`` (newest-first), ``total``, and ``counts`` by
        status.
    """
    ctx = _mcp.get_context()
    curatedb: CurateDB = ctx.request_context.lifespan_context.get("curatedb")
    if curatedb is None:
        raise ValueError("curate plugin is disabled")

    drafts = curatedb.list_all(status=status or None)
    return {
        "drafts": drafts,
        "total": len(drafts),
        "counts": curatedb.counts_by_status(),
    }
