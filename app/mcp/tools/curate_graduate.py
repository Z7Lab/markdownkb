"""MCP tool: graduate a reviewed curate draft into the corpus.

The gated analog of ``promote_to_wiki`` — write-gated (honors
``mcp.save_document`` and the target's ``writable: true``). Normally a
human graduates from the Curate tab; this tool exists so a cloud agent can
complete the loop when explicitly authorized to.
"""

from app.config import Settings
from app.plugins.curate.curatedb import CurateDB
from app.plugins.curate.service import CurateError, graduate

TOOL = {
    "name": "curate_graduate",
    "feature_flag": "save_document",
    "requires_plugin": "curate",
    "write": True,
}

_mcp = None  # Injected by register_tools()


def handler(
    draft_id: str,
    target_source: str = "",
    overwrite: bool = False,
) -> dict:
    """Graduate a draft into the canonical corpus.

    Writes the draft into a writable source at the path implied by its
    ``taxonomy_slot``, with provenance frontmatter, a log.md entry, and a
    version commit, then marks the draft ``graduated``. Refuses targets
    that are read-only or match ``global_ignore`` (which would be written
    but never indexed).

    Args:
        draft_id: Id of an open (``status=draft``) candidate.
        target_source: Writable source path to graduate into. Empty uses
                       the first writable source (normally knowledge_docs).
        overwrite: Replace an existing document at the target path.

    Returns:
        Dict with status, path, relative_path, target_source, log_path,
        and version_commit.
    """
    ctx = _mcp.get_context()
    settings: Settings = ctx.request_context.lifespan_context["settings"]
    curatedb: CurateDB = ctx.request_context.lifespan_context.get("curatedb")
    versioning_manager = ctx.request_context.lifespan_context.get("versioning_manager")
    if curatedb is None:
        raise ValueError("curate plugin is disabled")

    try:
        return graduate(
            curatedb=curatedb,
            settings=settings,
            draft_id=draft_id,
            target_source=target_source,
            overwrite=overwrite,
            versioning_manager=versioning_manager,
        )
    except CurateError as e:
        raise ValueError(str(e)) from e
