"""MCP tool: retrieve from the knowledge base via hybrid search."""

from app.mcp.history import record_search
from app.rag.retriever import Retriever

TOOL = {
    "name": "retrieve",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler(query: str, top_k: int = 5) -> dict:
    """Search the knowledge base using hybrid vector + keyword search.

    Returns ranked results with document content, source paths, and
    relevance scores.
    """
    ctx = _mcp.get_context()
    retriever: Retriever = ctx.request_context.lifespan_context["retriever"]

    results = retriever.search(query, top_k=top_k)
    formatted = [
        {
            "content": r.document,
            "source": r.metadata.get("source_path", ""),
            "score": round(r.score, 4),
        }
        for r in results
    ]

    record_search(ctx, query, formatted, tool_name="retrieve")

    return {
        "results": formatted,
        "total": len(results),
    }
