"""Standalone MCP server for MarkdownKB.

Exposes core MarkdownKB capabilities — search, chat, document listing, and
indexing — as MCP tools that any MCP-compatible client can call.

Tools are auto-discovered from ``app/mcp/tools/``.  Each tool module
exports a ``TOOL`` dict (with ``name`` and optional ``feature_flag``)
and a ``handler`` callable.  Feature-gated tools are only registered
when their flag is enabled in ``config/settings.yaml`` under ``mcp:``.

Run as a separate process alongside the FastAPI app::

    python mcp_server.py                  # stdio transport (default)
    python mcp_server.py --http           # Streamable HTTP on port 9715
    python mcp_server.py --http --port 8000

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
from app.logbuffer import log_buffer
from app.mcp import _state
from app.mcp.http_middleware import default_allowed_hosts, run_http_with_auth
from app.mcp.prompts import register_prompts
from app.mcp.resources import register_resources
from app.mcp.tools import register_tools
from app.rag.retriever import Retriever
from app.storage.chatdb import ChatDB
from app.storage.plandb import PlanDB
from app.storage.scopedb import ScopeDB
from app.storage.searchdb import SearchDB
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

_settings_for_loglevel = Settings.get()
# Install the request-id log factory before basicConfig so the format
# template can reference %(request_id)s without raising KeyError.
from app.logging_ctx import install_request_id_log_factory
install_request_id_log_factory()
logging.basicConfig(
    level=getattr(logging, _settings_for_loglevel.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s [rid=%(request_id)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logging.getLogger().addHandler(log_buffer)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Set up MarkdownKB services and expose them via the lifespan context.

    FastMCP's streamable-HTTP session manager calls this for every new client
    session.  All expensive work (model loading, VectorStore, ChromaDB, DBs)
    runs only on the first call and is cached in ``_state.cached_resources``.
    Subsequent sessions yield the cached dict immediately so the MCP handshake
    completes in milliseconds instead of seconds.
    """
    if _state.cached_resources is None:
        settings = Settings.get()
        load_models(settings.model_configs)

        store = VectorStore(settings.persist_directory, settings.collection_name)
        tracking = TrackingDB(settings.data_directory)

        if store.count == 0:
            logger.info("Empty store — running initial index")
            run_index(settings, store, tracking)

        retriever = Retriever(store, settings, tracking)

        plandb = PlanDB(settings.data_directory)
        scopedb = ScopeDB(settings.data_directory)

        tagdb = None
        if settings.plugin_enabled("tags"):
            from app.plugins.tags.tagdb import TagDB
            tagdb = TagDB(settings.data_directory)
            logger.info("TagDB initialized for MCP (tags plugin enabled)")

        kgdb = None
        if settings.plugin_enabled("knowledge_graph"):
            from app.storage.knowledgegraph import KnowledgeGraphDB
            kgdb = KnowledgeGraphDB(settings.data_directory)
            logger.info("KnowledgeGraphDB initialized for MCP (knowledge_graph plugin enabled)")

        bucket_service = None
        if settings.plugin_enabled("buckets"):
            from app.plugins.buckets.bucketdb import BucketDB
            from app.plugins.buckets.bucket_service import BucketService
            bucketdb = BucketDB(settings.data_directory)
            bucket_service = BucketService(
                bucketdb, settings.persist_directory, settings.embedding_model,
                remote_config=settings.embedding_remote_config,
            )
            bucket_service.flag_expired()
            logger.info("BucketService initialized for MCP (buckets plugin enabled)")

        wikidb = None
        if settings.plugin_enabled("wiki_compile"):
            from app.plugins.wiki_compile.wikidb import WikiDB
            wikidb = WikiDB(settings.data_directory)
            logger.info("WikiDB initialized for MCP (wiki_compile plugin enabled)")

        curatedb = None
        if settings.plugin_enabled("curate"):
            from app.plugins.curate.curatedb import CurateDB
            curatedb = CurateDB(settings.data_directory)
            logger.info("CurateDB initialized for MCP (curate plugin enabled)")

        versioning_manager = None
        if settings.versioning_enabled:
            try:
                from pathlib import Path
                from app.versioning import GitManager
                versioning_manager = GitManager(Path(settings.versioning_root))
                logger.info("GitManager initialized for MCP (versioning enabled)")
            except Exception:
                logger.warning("GitManager init failed for MCP", exc_info=True)

        chatdb = None
        searchdb = None
        if settings.mcp_enabled("track_history"):
            chatdb = ChatDB(settings.data_directory)
            searchdb = SearchDB(settings.data_directory)
            logger.info("MCP history tracking enabled (searches + chat threads)")

        _state.cached_resources = {
            "settings": settings,
            "store": store,
            "tracking": tracking,
            "retriever": retriever,
            "plandb": plandb,
            "scopedb": scopedb,
            "tagdb": tagdb,
            "chatdb": chatdb,
            "searchdb": searchdb,
            "bucket_service": bucket_service,
            "wikidb": wikidb,
            "curatedb": curatedb,
            "kgdb": kgdb,
            "versioning_manager": versioning_manager,
        }

        if not _state.tools_registered:
            registered = register_tools(server, settings)
            _state.tools_registered = True
            logger.info(
                "MCP server ready (%d documents indexed, %d tools: %s)",
                store.count, len(registered), registered,
            )
    else:
        logger.debug("MCP lifespan re-entered (new session) — reusing cached resources")

    yield _state.cached_resources


def _create_mcp(bind_host: str = "127.0.0.1", bind_port: int = 9715) -> FastMCP:
    """Create the FastMCP instance.

    Deferred from module level so that Settings.get() is not called as a side
    effect of importing this module (e.g. during tests or tool introspection).

    DNS rebinding protection is on by default. Its Host allowlist is seeded
    with every hostname this server is likely to be reached by (localhost,
    host.docker.internal, the machine's hostname + LAN IPs, and the explicit
    bind host if specific). Users can override via ``mcp.allowed_hosts`` —
    including ``*`` to turn the check off entirely.
    """
    settings = Settings.get()
    configured_hosts = settings.mcp_features.get("allowed_hosts", [])
    if not isinstance(configured_hosts, list):
        configured_hosts = []
    configured_origins = settings.mcp_features.get("allowed_origins", [])
    if not isinstance(configured_origins, list):
        configured_origins = []

    if "*" in configured_hosts or "*" in configured_origins:
        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )
    else:
        merged = [str(h) for h in configured_hosts]
        for h in default_allowed_hosts(bind_host, bind_port):
            if h not in merged:
                merged.append(h)
        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=merged,
            allowed_origins=[str(o) for o in configured_origins],
        )

    mcp = FastMCP(
        "markdownkb",
        instructions=(
            "MarkdownKB is a personal knowledge base of markdown documents. "
            "Use the search/retrieve tools for semantic search, the chat tool for "
            "RAG-grounded answers, list_files/read_file to browse documents, and "
            "deep_research for multi-angle synthesis. "
            "Resources: attach markdownkb://overview for a live KB summary, or attach "
            "a scope/directory/bucket resource to scope context to a specific area. "
            "Prompts: ask-kb, summarize-topic, and research-topic are ready-made "
            "starting points."
        ),
        lifespan=lifespan,
        transport_security=transport_security,
    )

    # Resources and prompts are static — register at creation time so they
    # are available immediately, not deferred to the first lifespan call.
    register_resources(mcp, settings)
    register_prompts(mcp, settings)

    return mcp


def main():
    parser = argparse.ArgumentParser(description="MarkdownKB MCP Server")
    parser.add_argument(
        "--http", action="store_true",
        help="Run with Streamable HTTP transport instead of stdio",
    )
    parser.add_argument(
        "--port", type=int, default=9715,
        help="Port for HTTP transport (default: 9715)",
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="Host for HTTP transport (default: 127.0.0.1)",
    )
    args = parser.parse_args()

    mcp = _create_mcp(bind_host=args.host, bind_port=args.port)

    if args.http:
        logger.info("Starting MCP server (Streamable HTTP) on %s:%d", args.host, args.port)
        run_http_with_auth(mcp, args.host, args.port)
    else:
        logger.info("Starting MCP server (stdio)")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
