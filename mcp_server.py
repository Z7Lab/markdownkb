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
from app.mcp.tools import register_tools
from app.rag.retriever import Retriever
from app.storage.chatdb import ChatDB
from app.storage.plandb import PlanDB
from app.storage.scopedb import ScopeDB
from app.storage.searchdb import SearchDB
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

_settings_for_loglevel = Settings.get()
logging.basicConfig(
    level=getattr(logging, _settings_for_loglevel.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
logging.getLogger().addHandler(log_buffer)
logger = logging.getLogger(__name__)

# Guard against FastMCP's streamable-HTTP session manager calling the lifespan
# context for every new session.  We only want to register tools once.
_tools_registered = False


# -- Lifespan: initialize core services once at startup --------------------

@asynccontextmanager
async def lifespan(server: FastMCP):
    """Set up MarkdownKB services and expose them via the lifespan context."""
    settings = Settings.get()
    load_models(settings.model_configs)

    store = VectorStore(settings.persist_directory, settings.collection_name)
    tracking = TrackingDB(settings.data_directory)

    if store.count == 0:
        logger.info("Empty store — running initial index")
        run_index(settings, store, tracking)

    retriever = Retriever(store, settings, tracking)

    # Core databases
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
        bucket_service.cleanup_expired()
        logger.info("BucketService initialized for MCP (buckets plugin enabled)")

    # Optional history tracking — record MCP calls to the web UI sidebar DBs
    chatdb = None
    searchdb = None
    if settings.mcp_enabled("track_history"):
        chatdb = ChatDB(settings.data_directory)
        searchdb = SearchDB(settings.data_directory)
        logger.info("MCP history tracking enabled (searches + chat threads)")

    # Auto-discover and register MCP tools (guard: session manager calls this
    # lifespan per-session in HTTP mode, but tools must only be registered once)
    global _tools_registered
    if not _tools_registered:
        registered = register_tools(server, settings)
        _tools_registered = True
        logger.info(
            "MCP server ready (%d documents indexed, %d tools: %s)",
            store.count, len(registered), registered,
        )
    else:
        logger.debug("MCP lifespan re-entered (new session) — tools already registered")

    yield {
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
        "kgdb": kgdb,
    }

    if kgdb:
        kgdb.close()
    if chatdb:
        chatdb.close()
    if searchdb:
        searchdb.close()
    if tagdb:
        tagdb.close()
    if bucket_service:
        bucket_service.db.close()
    scopedb.close()
    plandb.close()
    tracking.close()
    logger.info("MCP server shutdown")


# -- Entry point -----------------------------------------------------------

def _create_mcp() -> FastMCP:
    """Create the FastMCP instance.

    Deferred from module level so that Settings.get() is not called as a side
    effect of importing this module (e.g. during tests or tool introspection).
    """
    settings = Settings.get()
    allowed_hosts = settings.mcp_features.get("allowed_hosts", [])
    if not isinstance(allowed_hosts, list):
        allowed_hosts = []
    allowed_origins = settings.mcp_features.get("allowed_origins", [])
    if not isinstance(allowed_origins, list):
        allowed_origins = []

    # '*' in either list means "allow all" — disable DNS rebinding protection entirely.
    # This covers both Host and Origin checks with a single wildcard.
    if "*" in allowed_hosts or "*" in allowed_origins:
        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )
    else:
        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[str(h) for h in allowed_hosts],
            allowed_origins=[str(o) for o in allowed_origins],
        )

    return FastMCP(
        "markdownkb",
        instructions=(
            "MarkdownKB is a personal markdown knowledge base. Use the tools below to "
            "search indexed documents, retrieve full file contents, list indexed "
            "files, generate implementation plans, and trigger re-indexing."
        ),
        lifespan=lifespan,
        transport_security=transport_security,
    )


def _run_http_with_auth(mcp: FastMCP, host: str, port: int):
    """Run Streamable HTTP transport with optional API key middleware.

    Middleware stack (outermost → innermost):
      CORSMiddleware        — adds CORS headers; handles OPTIONS preflight
      McpApiKeyMiddleware   — rejects requests without valid key (if configured)
      _WithUtilityRoutes    — intercepts /logs and /log-level
      mcp_asgi              — FastMCP with DNS rebinding protection on /mcp

    CORS must be outermost so OPTIONS preflight responses are served without
    hitting auth middleware, which is standard browser CORS behaviour.
    """
    import anyio
    import uvicorn
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    async def _serve():
        mcp.settings.host = host
        mcp.settings.port = port
        mcp_asgi = mcp.streamable_http_app()

        class _WithUtilityRoutes:
            """Thin ASGI wrapper: intercepts /logs and /log-level; forwards everything
            else (including lifespan) to the inner MCP app unchanged."""

            def __init__(self, inner):
                self._inner = inner

            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    path = scope.get("path", "")
                    if path == "/logs":
                        await self._handle_logs(scope, receive, send)
                        return
                    if path == "/log-level":
                        await self._handle_log_level(scope, receive, send)
                        return
                await self._inner(scope, receive, send)

            async def _handle_logs(self, scope, receive, send):
                request = Request(scope, receive)
                if request.method == "DELETE":
                    log_buffer.clear()
                    response = JSONResponse({"status": "cleared"})
                else:
                    since = int(request.query_params.get("since", 0))
                    entries, seq = log_buffer.get_entries(since)
                    response = JSONResponse({"entries": entries, "seq": seq})
                await response(scope, receive, send)

            async def _handle_log_level(self, scope, receive, send):
                request = Request(scope, receive)
                if request.method == "PUT":
                    body = await request.json()
                    level_str = body.get("level", "INFO").upper()
                    level = getattr(logging, level_str, logging.INFO)
                    logging.getLogger().setLevel(level)
                    logger.info("MCP log level changed to %s", level_str)
                    response = JSONResponse({"level": level_str})
                else:
                    level_name = logging.getLevelName(logging.getLogger().level)
                    response = JSONResponse({"level": level_name})
                await response(scope, receive, send)

        combined_app = _WithUtilityRoutes(mcp_asgi)

        settings = Settings.get()
        api_key = settings.api_key

        # Auth middleware — wraps utility routes + MCP app
        if api_key:
            from app.mcp.auth import McpApiKeyMiddleware
            combined_app = McpApiKeyMiddleware(combined_app, api_key)
            logger.info(
                "MCP auth enabled (accepts Authorization: Bearer, X-MarkdownKB-Key, or ?token=)"
            )
        else:
            logger.info("MCP auth disabled (no API key configured)")

        # CORS — outermost so OPTIONS preflight is answered before auth.
        # Derive allowed origins from settings: '*' → allow all.
        allowed_origins_setting = settings.mcp_features.get("allowed_origins", []) or []
        allowed_hosts_setting = settings.mcp_features.get("allowed_hosts", []) or []
        if "*" in allowed_origins_setting or "*" in allowed_hosts_setting:
            cors_origins = ["*"]
        elif allowed_origins_setting:
            cors_origins = [str(o) for o in allowed_origins_setting]
        else:
            cors_origins = ["*"]  # default permissive for LAN deployments
        combined_app = CORSMiddleware(
            combined_app,
            allow_origins=cors_origins,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["*"],
        )
        logger.info("MCP CORS enabled (origins: %s)", cors_origins)

        config = uvicorn.Config(
            combined_app, host=host, port=port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()

    anyio.run(_serve)


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

    mcp = _create_mcp()

    if args.http:
        logger.info("Starting MCP server (Streamable HTTP) on %s:%d", args.host, args.port)
        _run_http_with_auth(mcp, args.host, args.port)
    else:
        logger.info("Starting MCP server (stdio)")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
