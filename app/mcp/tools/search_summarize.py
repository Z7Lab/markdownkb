"""MCP tool: search and summarize results using the LLM."""

from app.config import Settings
from app.rag.retriever import Retriever

TOOL = {
    "name": "search_summarize",
    "feature_flag": None,
    "requires_plugin": "search",
}

_mcp = None  # Injected by register_tools()


def handler(query: str, top_k: int = 5) -> dict:
    """Search the knowledge base and return an LLM-generated summary.

    Retrieves relevant chunks, builds a context window, and asks the
    configured LLM to synthesize a concise answer.  Use this when you
    want a natural-language summary rather than raw search results.

    Args:
        query: The question or topic to search and summarize.
        top_k: Number of chunks to retrieve for context (default 5).
    """
    from app.rag.llm import get_completion
    from app.rag.prompts import get_search_summary_system, get_search_summary_user

    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    retriever: Retriever = deps["retriever"]
    settings: Settings = deps["settings"]

    results = retriever.search(query, top_k=top_k)
    if not results:
        return {"summary": "No relevant documents found.", "sources": []}

    # Build context from search results
    context_parts = []
    sources = []
    for r in results:
        src = r.metadata.get("source_path", "")
        context_parts.append(r.document)
        if src and src not in sources:
            sources.append(src)

    context = "\n\n---\n\n".join(context_parts)

    kgdb = deps.get("kgdb")
    if kgdb is not None:
        kg_ctx = kgdb.context_for_query(query)
        if kg_ctx:
            context += "\n\n" + kg_ctx

    messages = [
        {"role": "system", "content": get_search_summary_system()},
        {"role": "user", "content": get_search_summary_user().format(
            context=context, query=query,
        )},
    ]

    summary = get_completion(messages, settings)

    return {
        "summary": summary,
        "sources": sources,
        "chunks_used": len(results),
    }
