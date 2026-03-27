"""Optional history tracking for MCP tool calls.

When ``mcp.track_history`` is enabled, MCP search and chat calls are
recorded to the same SQLite databases that the web UI uses for sidebar
history.  Entries are labeled with source ``"agent"`` so the frontend
can distinguish them from interactive sessions.

This module talks directly to the storage layer (ChatDB, SearchDB) and
does NOT import any plugin code — keeping MCP decoupled from plugin
internals.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _get_db(ctx: Any, key: str):
    """Return a DB instance from the MCP lifespan context, or None."""
    return ctx.request_context.lifespan_context.get(key)


def record_search(
    ctx: Any,
    query: str,
    results: list[dict],
    *,
    tool_name: str = "search",
    result_details: list[dict] | None = None,
    result_data: list[dict] | None = None,
) -> str | None:
    """Record an MCP search call to SearchDB (sidebar history).

    Returns the search_id if recorded, None if history tracking is off.
    """
    searchdb = _get_db(ctx, "searchdb")
    if searchdb is None:
        return None

    result_paths = [r.get("source", r.get("path", "")) for r in results]
    result_count = len(results)

    try:
        search_id = searchdb.save_search(
            query,
            result_paths=result_paths,
            result_count=result_count,
            result_details=result_details,
            result_data=result_data,
            source="agent",
        )
        logger.debug("MCP %s recorded to history: %s (id=%s)", tool_name, query, search_id)
        return search_id
    except Exception:
        logger.warning("Failed to record MCP %s to history", tool_name, exc_info=True)
        return None


def record_chat(
    ctx: Any,
    message: str,
    response: str,
    *,
    sources: list[str] | None = None,
    source_map: dict[str, str] | None = None,
) -> str | None:
    """Record an MCP chat call to ChatDB (thread sidebar).

    Creates a thread titled with a short version of the message, then
    adds the user message and assistant response with sources.

    Returns the thread_id if recorded, None if history tracking is off.
    """
    chatdb = _get_db(ctx, "chatdb")
    if chatdb is None:
        return None

    try:
        # Use first ~50 chars of the message as the thread title
        title = message[:50].strip()
        if len(message) > 50:
            title += "..."
        title = f"[agent] {title}"

        thread_id = chatdb.create_thread(title)
        chatdb.add_message(thread_id, "user", message)
        chatdb.add_message(thread_id, "assistant", response)
        if sources:
            chatdb.set_sources(thread_id, "assistant", sources, source_map or None)
        logger.debug("MCP chat recorded to history: thread=%s", thread_id)
        return thread_id
    except Exception:
        logger.warning("Failed to record MCP chat to history", exc_info=True)
        return None
