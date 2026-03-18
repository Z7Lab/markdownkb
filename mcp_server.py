"""Standalone MCP server for MDKB.

Exposes core MDKB capabilities — search, chat, document listing, and
indexing — as MCP tools that any MCP-compatible client can call.

Tools are auto-discovered from ``app/mcp/tools/``.  Each tool module
exports a ``TOOL`` dict (with ``name`` and optional ``feature_flag``)
and a ``handler`` callable.  Feature-gated tools are only registered
when their flag is enabled in ``config/settings.yaml`` under ``mcp:``.

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
from mcp.server.transport_security import TransportSecuritySettings

from app.config import Settings
from app.embeddings.registry import load_models
from app.ingestion.indexer import run_index
from app.mcp.tools import register_tools
from app.rag.retriever import Retriever
from app.storage.chatdb import ChatDB
from app.storage.plandb import PlanDB
from app.storage.searchdb import SearchDB
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
    load_models(settings.model_configs)

    store = VectorStore(settings.persist_directory, settings.collection_name)
    tracking = TrackingDB(settings.data_directory)

    if store.count == 0:
        logger.info("Empty store — running initial index")
        run_index(settings, store, tracking)

    retriever = Retriever(store, settings, tracking)

    # Plan storage — shared with the web UI planner plugin
    plandb = PlanDB(settings.data_directory)

    # Optional history tracking — record MCP calls to the web UI sidebar DBs
    chatdb = None
    searchdb = None
    if settings.mcp_enabled("track_history"):
        chatdb = ChatDB(settings.data_directory)
        searchdb = SearchDB(settings.data_directory)
        logger.info("MCP history tracking enabled (searches + chat threads)")

    # Auto-discover and register MCP tools
    registered = register_tools(mcp, settings)
    logger.info(
        "MCP server ready (%d documents indexed, %d tools: %s)",
        store.count, len(registered), registered,
    )

    yield {
        "settings": settings,
        "store": store,
        "tracking": tracking,
        "retriever": retriever,
        "plandb": plandb,
        "chatdb": chatdb,
        "searchdb": searchdb,
    }

    if chatdb:
        chatdb.close()
    if searchdb:
        searchdb.close()
    plandb.close()
    tracking.close()
    logger.info("MCP server shutdown")


mcp = FastMCP(
    "mdkb",
    instructions=(
        "MDKB is a personal markdown knowledge base. Use the tools below to "
        "search indexed documents, retrieve full file contents, list indexed "
        "files, generate implementation plans, and trigger re-indexing."
    ),
    lifespan=lifespan,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


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
