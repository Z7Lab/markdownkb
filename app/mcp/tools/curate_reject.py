"""MCP tool: reject a curate draft (discard a bucket-C candidate)."""

from app.plugins.curate.curatedb import CurateDB
from app.plugins.curate.service import CurateError, reject

TOOL = {
    "name": "curate_reject",
    "feature_flag": None,
    "requires_plugin": "curate",
    "write": True,
}

_mcp = None  # Injected by register_tools()


def handler(draft_id: str, reason: str = "") -> dict:
    """Reject a draft. The record is kept (status=rejected) for provenance
    and is never written to the corpus.

    Args:
        draft_id: Id of the draft to reject.
        reason: Optional note on why it was rejected.

    Returns:
        Dict with status, draft_id, and reason.
    """
    ctx = _mcp.get_context()
    curatedb: CurateDB = ctx.request_context.lifespan_context.get("curatedb")
    if curatedb is None:
        raise ValueError("curate plugin is disabled")

    try:
        return reject(curatedb=curatedb, draft_id=draft_id, reason=reason)
    except CurateError as e:
        raise ValueError(str(e)) from e
