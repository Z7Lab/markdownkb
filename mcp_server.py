"""Standalone MCP server for MDKB.

Exposes core MDKB capabilities — search, chat, document listing, and
indexing — as MCP tools that any MCP-compatible client can call.

Run as a separate process alongside the FastAPI app::

    python mcp_server.py              # stdio transport (default)
    python mcp_server.py --sse        # SSE transport on port 9715

The server imports core services directly — it does NOT proxy through the
FastAPI HTTP layer.
"""

import argparse
import logging
import sys
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from app.config import Settings
from app.ingestion.indexer import run_index
from app.rag.retriever import Retriever
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# -- Lifespan: initialize core services once at startup --------------------

@asynccontextmanager
async def lifespan(server: FastMCP):
    """Set up MDKB services and expose them via the lifespan context."""
    settings = Settings.get()

    store = VectorStore(settings.persist_directory, settings.collection_name)
    tracking = TrackingDB(settings.data_directory)

    if store.count == 0:
        logger.info("Empty store — running initial index")
        run_index(settings, store, tracking)

    retriever = Retriever(store, settings, tracking)

    logger.info(
        "MCP server ready (%d documents indexed)",
        store.count,
    )
    yield {
        "settings": settings,
        "store": store,
        "tracking": tracking,
        "retriever": retriever,
    }

    tracking.close()
    logger.info("MCP server shutdown")


mcp = FastMCP(
    "mdkb",
    instructions=(
        "MDKB is a personal markdown knowledge base. Use the tools below to "
        "search indexed documents, retrieve full file contents, list indexed "
        "files, and trigger re-indexing."
    ),
    lifespan=lifespan,
)


# -- Tools -----------------------------------------------------------------

@mcp.tool()
def search(query: str, top_k: int = 5) -> dict:
    """Search the knowledge base using hybrid vector + keyword search.

    Returns ranked results with document content, source paths, and
    relevance scores.
    """
    ctx = mcp.get_context()
    retriever: Retriever = ctx.request_context.lifespan_context["retriever"]

    results = retriever.search(query, top_k=top_k)
    return {
        "results": [
            {
                "content": r.document,
                "source": r.metadata.get("source_path", ""),
                "score": round(r.score, 4),
            }
            for r in results
        ],
        "total": len(results),
    }


@mcp.tool()
def get_document(path: str) -> dict:
    """Read the full content of an indexed markdown file by its path."""
    from pathlib import Path as P

    ctx = mcp.get_context()
    settings: Settings = ctx.request_context.lifespan_context["settings"]
    tracking: TrackingDB = ctx.request_context.lifespan_context["tracking"]

    resolved = str(P(path).resolve())

    # Verify the file belongs to a configured source
    in_source = any(
        resolved.startswith(str(P(s).resolve()))
        for s in settings.sources
    )
    if not in_source:
        return {"error": "Path is not within a configured source directory"}

    record = tracking.get_file(resolved)
    if not record:
        return {"error": "File is not indexed"}

    try:
        content = P(resolved).read_text(encoding="utf-8")
    except OSError as exc:
        return {"error": f"Cannot read file: {exc}"}

    return {
        "path": resolved,
        "content": content,
        "status": record.get("status", "unknown"),
        "chunk_count": record.get("chunk_count", 0),
    }


@mcp.tool()
def list_documents(status: str = "") -> dict:
    """List all indexed documents.

    Optionally filter by status: 'complete', 'pending', 'error'.
    """
    ctx = mcp.get_context()
    tracking: TrackingDB = ctx.request_context.lifespan_context["tracking"]

    files = tracking.get_all_files()
    if status:
        files = [f for f in files if f.get("status") == status]

    return {
        "documents": [
            {
                "path": f["path"],
                "status": f.get("status", "unknown"),
                "chunk_count": f.get("chunk_count", 0),
            }
            for f in files
        ],
        "total": len(files),
    }


@mcp.tool()
def index_file(path: str) -> dict:
    """Re-index a single markdown file, updating the vector store."""
    from app.ingestion.watcher import reindex_file

    ctx = mcp.get_context()
    deps = ctx.request_context.lifespan_context
    settings: Settings = deps["settings"]
    store: VectorStore = deps["store"]
    tracking: TrackingDB = deps["tracking"]

    from pathlib import Path as P
    resolved = str(P(path).resolve())

    if not resolved.endswith(".md"):
        return {"error": "Only .md files can be indexed"}

    in_source = any(
        resolved.startswith(str(P(s).resolve()))
        for s in settings.sources
    )
    if not in_source:
        return {"error": "File is not within a configured source directory"}

    reindex_file(resolved, settings, store, tracking)

    record = tracking.get_file(resolved)
    return {
        "status": record.get("status", "unknown") if record else "not_found",
        "chunk_count": record.get("chunk_count", 0) if record else 0,
        "path": resolved,
    }


@mcp.tool()
def chat(message: str) -> dict:
    """Ask a question and get an answer grounded in your knowledge base.

    Uses RAG to find relevant documents and generate a contextual response
    via the configured LLM.
    """
    from app.services.chat_service import chat_respond

    ctx = mcp.get_context()
    deps = ctx.request_context.lifespan_context
    retriever: Retriever = deps["retriever"]
    settings: Settings = deps["settings"]

    # Collect the streaming response into a single string
    response = ""
    for chunk in chat_respond(message, retriever, settings):
        response = chunk

    return {"response": response}


@mcp.tool()
def list_sources() -> dict:
    """List all configured source directories being watched."""
    ctx = mcp.get_context()
    settings: Settings = ctx.request_context.lifespan_context["settings"]
    return {"sources": settings.sources}


@mcp.tool()
def stats() -> dict:
    """Get knowledge base statistics — document counts, index status."""
    ctx = mcp.get_context()
    tracking: TrackingDB = ctx.request_context.lifespan_context["tracking"]
    store: VectorStore = ctx.request_context.lifespan_context["store"]

    return {
        **tracking.get_stats(),
        "vector_count": store.count,
    }


# -- Entry point -----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="MDKB MCP Server")
    parser.add_argument(
        "--sse", action="store_true",
        help="Run with SSE transport instead of stdio",
    )
    parser.add_argument(
        "--port", type=int, default=9715,
        help="Port for SSE transport (default: 9715)",
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="Host for SSE transport (default: 127.0.0.1)",
    )
    args = parser.parse_args()

    if args.sse:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        logger.info("Starting MCP server (SSE) on %s:%d", args.host, args.port)
        mcp.run(transport="sse")
    else:
        logger.info("Starting MCP server (stdio)")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
