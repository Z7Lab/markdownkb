"""MCP tool: enhance a search query using LLM keyword extraction."""

from app.config import Settings

TOOL = {
    "name": "enhance_query",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler(query: str) -> dict:
    """Enhance a search query by extracting keywords and expanding acronyms.

    Uses the LLM to identify critical keywords, expand acronyms
    (e.g. ENS -> Ethereum Name Service), and determine semantic context.
    Useful for improving retrieval quality before calling retrieve.

    Args:
        query: The raw search query to enhance.
    """
    from app.services.query_service import enhance_query

    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    settings: Settings = deps["settings"]

    result = enhance_query(query, settings)

    return {
        "original": result.original,
        "keywords": result.keywords,
        "expanded_terms": result.expanded_terms,
        "context": result.context,
        "error": result.error,
    }
