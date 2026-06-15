"""MCP tool: submit a bucket-C candidate as a curate draft.

This is the agent-facing end of the analyze–match–codify loop. After the
agent sorts a source's patterns into A/B/C (using the existing ``search`` /
``bucket-search`` tools), it calls this once per bucket-C finding. The
draft lands as ``status=draft`` — nothing touches the live corpus until a
human graduates it via the Curate tab.
"""

from app.plugins.curate.curatedb import CurateDB
from app.plugins.curate.service import CurateError, submit_draft

TOOL = {
    "name": "curate_submit_draft",
    "feature_flag": None,
    "requires_plugin": "curate",
    "write": True,
}

_mcp = None  # Injected by register_tools()


def handler(
    title: str,
    body_md: str,
    taxonomy_slot: str,
    source_type: str = "",
    source_ref: str = "",
    run_id: str = "",
) -> dict:
    """File a practiced-but-uncodified (bucket-C) pattern as a review draft.

    Call this for each bucket-C finding from an analyze–match–codify pass.
    The draft is held for human review; it does NOT enter the corpus until
    a curator graduates it. A good draft body carries: the general,
    source-independent pattern; why it works / what it prevents; a worked
    example with real anchors kept as the example; and honest TODOs for
    anything the source didn't support.

    Args:
        title: Short name for the pattern.
        body_md: Markdown body. Include the general pattern, rationale, a
                 worked example, and honest TODOs — thin bodies are flagged
                 in ``shape_warnings``.
        taxonomy_slot: Corpus path the draft graduates into, e.g.
                       ``patterns/error-handling``. Required — it determines
                       where the doc lands.
        source_type: Origin kind — ``code`` or ``bucket``.
        source_ref: Origin reference — a repo path or a bucket id.
        run_id: Optional correlation id tying drafts from one analysis run.

    Returns:
        Dict with the created ``draft`` and any ``shape_warnings``.
    """
    ctx = _mcp.get_context()
    curatedb: CurateDB = ctx.request_context.lifespan_context.get("curatedb")
    if curatedb is None:
        raise ValueError("curate plugin is disabled")

    try:
        return submit_draft(
            curatedb=curatedb,
            title=title,
            body_md=body_md,
            taxonomy_slot=taxonomy_slot,
            source_type=source_type,
            source_ref=source_ref,
            run_id=run_id or None,
        )
    except CurateError as e:
        raise ValueError(str(e)) from e
