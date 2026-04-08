"""MCP tool: RAG-powered chat with the knowledge base."""

from app.config import Settings
from app.mcp.history import record_chat
from app.mcp.scope import resolve_mcp_scope
from app.rag.retriever import Retriever

TOOL = {
    "name": "chat",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler(message: str, scope_id: str | None = None,
            thread_id: str | None = None) -> dict:
    """Ask a question and get an answer grounded in your knowledge base.

    Uses RAG to find relevant documents and generate a contextual response
    via the configured LLM. The response includes a ``sources`` list of
    file paths that were used as context — use ``get_file(path)`` to read
    any cited source in full.

    Args:
        message: Question or message to answer.
        scope_id: Optional scope ID to restrict search to specific folders
                  and/or tags.  Use the list_scopes tool to discover
                  available scopes.
        thread_id: Optional thread ID for multi-turn conversation.  Pass
                   the thread_id from a previous response to continue the
                   conversation with history.  Omit to start a new thread.
                   Requires mcp.track_history to be enabled.
    """
    from app.services.chat_service import chat_respond

    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    retriever: Retriever = deps["retriever"]
    settings: Settings = deps["settings"]
    chatdb = deps.get("chatdb")

    # Resolve scope into folder filter + allowed paths
    folders_filter, allowed_paths, exclude_patterns = resolve_mcp_scope(ctx, scope_id)

    # Thread support: create or reuse thread when ChatDB is available
    actual_thread_id = thread_id
    if chatdb and not actual_thread_id:
        from app.utils import short_title
        title = short_title(message)
        actual_thread_id = chatdb.create_thread(title)

    # Collect the streaming response into a single string
    sources: list[str] = []
    source_map: dict[str, str] = {}
    response = ""
    for chunk in chat_respond(
        message, retriever, settings,
        chatdb=chatdb,
        thread_id=actual_thread_id,
        folders_filter=folders_filter,
        allowed_paths=allowed_paths,
        exclude_patterns=exclude_patterns,
        sources_out=sources, source_map_out=source_map,
    ):
        response = chunk

    record_chat(ctx, message, response, sources=sources, source_map=source_map)

    result: dict = {
        "response": response, "sources": sources, "source_map": source_map,
    }
    if actual_thread_id:
        result["thread_id"] = actual_thread_id
    if scope_id:
        result["scope_id"] = scope_id
    return result
