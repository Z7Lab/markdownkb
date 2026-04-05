"""Scope resolution for MCP tools.

Resolves a ``scope_id`` from an MCP tool call into the
``folders_filter`` and ``allowed_paths`` parameters that
:meth:`Retriever.search` accepts.

Uses :func:`resolve_scopes_raw` (raises ``ValueError``, not
``HTTPException``) and calls ``TagDB.get_paths_for_tags`` directly
rather than going through ``tag_utils`` (whose resolver callback is
only registered by the FastAPI tags plugin startup, not the MCP
lifespan).
"""

from typing import Any

from app.scope_utils import resolve_scopes_raw
from app.storage.scopedb import ScopeDB


def resolve_mcp_scope(
    ctx: Any,
    scope_id: str | None,
    *,
    ad_hoc_tags: list[str] | None = None,
) -> tuple[list[str] | None, set[str] | None]:
    """Resolve a scope_id (and optional ad-hoc tags) for an MCP tool.

    Returns ``(folders_filter, allowed_paths)`` ready to pass to
    ``Retriever.search()``, ``chat_respond()``, ``run_planner()``, etc.

    Raises ``ValueError`` if the scope_id is not found.
    """
    deps = ctx.request_context.lifespan_context
    scopedb: ScopeDB | None = deps.get("scopedb")

    folders_filter = None
    scope_tags: list[str] | None = None

    if scope_id and scopedb:
        folders_filter, scope_tags = resolve_scopes_raw([scope_id], scopedb)

    # Merge scope tags + ad-hoc tags, then resolve to file paths via TagDB
    all_tags: set[str] = set()
    if scope_tags:
        all_tags.update(scope_tags)
    if ad_hoc_tags:
        all_tags.update(ad_hoc_tags)

    allowed_paths: set[str] | None = None
    if all_tags:
        tagdb = deps.get("tagdb")
        if tagdb is not None:
            allowed_paths = tagdb.get_paths_for_tags(all_tags)

    return folders_filter, allowed_paths
