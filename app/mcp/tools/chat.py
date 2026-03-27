"""MCP tool: RAG-powered chat with the knowledge base."""

from app.config import Settings
from app.mcp.history import record_chat
from app.rag.retriever import Retriever

TOOL = {
    "name": "chat",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler(message: str) -> dict:
    """Ask a question and get an answer grounded in your knowledge base.

    Uses RAG to find relevant documents and generate a contextual response
    via the configured LLM.
    """
    from app.services.chat_service import chat_respond

    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    retriever: Retriever = deps["retriever"]
    settings: Settings = deps["settings"]

    # Collect the streaming response into a single string
    sources: list[str] = []
    source_map: dict[str, str] = {}
    response = ""
    for chunk in chat_respond(
        message, retriever, settings,
        sources_out=sources, source_map_out=source_map,
    ):
        response = chunk

    record_chat(ctx, message, response, sources=sources, source_map=source_map)

    return {"response": response, "sources": sources, "source_map": source_map}
