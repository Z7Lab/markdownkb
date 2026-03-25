"""MCP tool: retrieve from the knowledge base via hybrid search."""

from app.mcp.history import record_search
from app.rag.retriever import Retriever

TOOL = {
    "name": "retrieve",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler(query: str, top_k: int = 5, tags: list[str] | None = None) -> dict:
    """Search the knowledge base using hybrid vector + keyword search.

    Returns ranked results with document content, source paths, and
    relevance scores.  Optionally filter results to documents matching
    any of the given tags.

    Args:
        query: Search query string.
        top_k: Maximum number of results to return (default 5).
        tags: Optional list of tags to filter by (OR logic — documents
              matching any tag are included).  Use the list_tags tool
              to discover available tags.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    retriever: Retriever = deps["retriever"]

    # Resolve tags to allowed file paths via TagDB
    allowed_paths = None
    if tags:
        tagdb = deps.get("tagdb")
        if tagdb is not None:
            allowed_paths = tagdb.get_paths_for_tags(set(tags))
            if not allowed_paths:
                return {"results": [], "total": 0, "tags_filter": tags}

    results = retriever.search(query, top_k=top_k, allowed_paths=allowed_paths)
    formatted = [
        {
            "content": r.document,
            "source": r.metadata.get("source_path", ""),
            "score": round(r.score, 4),
        }
        for r in results
    ]

    record_search(ctx, query, formatted, tool_name="retrieve")

    response = {
        "results": formatted,
        "total": len(results),
    }
    if tags:
        response["tags_filter"] = tags
    return response
