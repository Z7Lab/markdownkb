"""MCP tool: retrieve from the knowledge base via hybrid search."""

from app.mcp.history import record_search
from app.mcp.scope import resolve_mcp_scope
from app.rag.retriever import Retriever

TOOL = {
    "name": "retrieve",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler(query: str, top_k: int = 5, tags: list[str] | None = None,
            scope_id: str | None = None) -> dict:
    """Search the knowledge base using hybrid vector + keyword search.

    Returns ranked results with document content, source paths, and
    relevance scores.  Optionally filter results by scope, tags, or both.

    Args:
        query: Search query string.
        top_k: Maximum number of results to return (default 5).
        tags: Optional list of tags to filter by (OR logic — documents
              matching any tag are included).  Use the list_tags tool
              to discover available tags.
        scope_id: Optional scope ID to restrict search to specific folders
                  and/or tags.  Use the list_scopes tool to discover
                  available scopes.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    retriever: Retriever = deps["retriever"]

    # Resolve scope + ad-hoc tags into folder filter and allowed paths
    folders_filter, allowed_paths = resolve_mcp_scope(
        ctx, scope_id, ad_hoc_tags=tags,
    )

    # If tags were given but resolved to zero matching paths, short-circuit
    if (tags or scope_id) and allowed_paths is not None and not allowed_paths:
        response: dict = {"results": [], "total": 0}
        if tags:
            response["tags_filter"] = tags
        if scope_id:
            response["scope_id"] = scope_id
        return response

    results = retriever.search(
        query, top_k=top_k,
        folders_filter=folders_filter, allowed_paths=allowed_paths,
    )
    formatted = [
        {
            "content": r.document,
            "source": r.metadata.get("source_path", ""),
            "score": round(r.score, 4),
        }
        for r in results
    ]

    # Build rich history data matching the web UI search format
    result_details = [
        {"path": r.metadata.get("source_path", ""), "score": r.score}
        for r in results
    ]
    result_data = [
        {
            "document": r.document,
            "snippets": [{"text": r.document, "score": r.score, "heading": r.metadata.get("heading", "")}],
            "metadata": dict(r.metadata),
            "score": r.score,
            "chunk_count": 1,
            "score_min": r.score,
            "score_max": r.score,
            "score_avg": r.score,
        }
        for r in results
    ]

    record_search(
        ctx, query, formatted, tool_name="retrieve",
        result_details=result_details, result_data=result_data,
    )

    response: dict = {
        "results": formatted,
        "total": len(results),
    }
    if tags:
        response["tags_filter"] = tags
    if scope_id:
        response["scope_id"] = scope_id
    return response
