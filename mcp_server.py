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


# -- Resources -----------------------------------------------------------------

def _slugify(name: str) -> str:
    """Convert a name to a URI-safe slug."""
    import re
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-") or "unnamed"


def _register_resources(server: FastMCP, settings) -> None:
    """Register MCP resources: static source-directory listings + file template."""
    from pathlib import Path

    # Static resources: one per configured source directory so clients can
    # browse the top-level structure without listing every file.
    # Use a factory to close over loop variables without adding function
    # parameters (any params on a resource fn → FastMCP treats it as a template).
    def _make_listing(source_path: str, source_name: str):
        def _listing() -> str:
            src = Path(source_path)
            if not src.exists():
                return f"Source directory not found: {source_path}"
            files = sorted(src.rglob("*.md"))
            lines = [f"# Source: {source_name}", f"Path: {source_path}", ""]
            lines += [str(f.relative_to(src)) for f in files[:500]]
            if len(files) > 500:
                lines.append(f"... and {len(files) - 500} more")
            return "\n".join(lines)
        return _listing

    for source_path in settings.sources:
        p = Path(source_path)
        uri = f"markdownkb://watch-directories/{p.name}"
        server.resource(
            uri,
            name=p.name,
            description=f"Watched directory: {source_path}",
            mime_type="text/plain",
        )(_make_listing(source_path, p.name))

    # Scope resources: one per named scope, listing files from its folders.
    from app.storage.scopedb import ScopeDB

    def _make_scope_listing(scope_id: str, scope_name: str, folders: list[str], tags: list[str]):
        def _listing() -> str:
            # Re-read scope live in case it was updated since registration
            scopedb = ScopeDB(settings.data_directory)
            try:
                scope = scopedb.get(scope_id)
            finally:
                scopedb.close()
            if scope is None:
                return f"Scope '{scope_name}' no longer exists."
            current_folders = scope["folders"]
            current_tags = scope["tags"]
            lines = [f"# Scope: {scope_name}"]
            if current_folders:
                lines.append(f"Folders: {', '.join(current_folders)}")
            if current_tags:
                lines.append(f"Tags: {', '.join(current_tags)}")
            lines.append("")
            files = []
            for folder in current_folders:
                p = Path(folder)
                if p.is_dir():
                    files.extend(sorted(p.rglob("*.md")))
            if not files:
                lines.append("(no files found in scope folders)")
            else:
                lines += [str(f) for f in files[:500]]
                if len(files) > 500:
                    lines.append(f"... and {len(files) - 500} more")
            return "\n".join(lines)
        return _listing

    try:
        _scopedb = ScopeDB(settings.data_directory)
        _scopes = _scopedb.list_scopes()
        _scopedb.close()
    except Exception:
        _scopes = []

    for scope in _scopes:
        _sid = scope["id"]
        _sname = scope["name"]
        _folders = scope.get("folders", [])
        _tags = scope.get("tags", [])
        _desc = f"Scope '{_sname}'"
        if _folders:
            _desc += f" — folders: {', '.join(_folders)}"
        if _tags:
            _desc += f" — tags: {', '.join(_tags)}"
        server.resource(
            f"markdownkb://scopes/{_slugify(_sname)}",
            name=_sname,
            description=_desc,
            mime_type="text/plain",
        )(_make_scope_listing(_sid, _sname, _folders, _tags))

    # Bucket resources: one per bucket, listing its indexed files.
    if settings.plugin_enabled("buckets"):
        from app.plugins.buckets.bucketdb import BucketDB
        import json as _json

        def _make_bucket_listing(bucket_id: str, bucket_name: str):
            def _listing() -> str:
                bucketdb = BucketDB(settings.data_directory)
                try:
                    bucket = bucketdb.get(bucket_id)
                finally:
                    bucketdb.close()
                if bucket is None:
                    return f"Bucket '{bucket_name}' no longer exists."
                sources = _json.loads(bucket.get("sources", "[]"))
                lines = [
                    f"# Bucket: {bucket_name}",
                    f"Files: {bucket['file_count']}  Chunks: {bucket['chunk_count']}",
                    "",
                ]
                for src in sources:
                    path = src.get("path", "")
                    glob = src.get("glob", "**/*.md")
                    lines.append(f"Source: {path}  ({glob})")
                    p = Path(path)
                    if p.is_dir():
                        files = sorted(p.glob(glob))
                        lines += [f"  {f}" for f in files[:200]]
                        if len(files) > 200:
                            lines.append(f"  ... and {len(files) - 200} more")
                    elif p.is_file():
                        lines.append(f"  {path}")
                return "\n".join(lines)
            return _listing

        try:
            _bucketdb = BucketDB(settings.data_directory)
            _buckets = _bucketdb.list_all()
            _bucketdb.close()
        except Exception:
            _buckets = []

        for bucket in _buckets:
            _bid = bucket["id"]
            _bname = bucket["name"]
            server.resource(
                f"markdownkb://buckets/{_slugify(_bname)}",
                name=_bname,
                description=f"Temporary bucket '{_bname}' — {bucket['file_count']} files, {bucket['chunk_count']} chunks",
                mime_type="text/plain",
            )(_make_bucket_listing(_bid, _bname))

    # Resource template: read any indexed file by path.
    @server.resource(
        "markdownkb://file/{path}",
        name="File",
        description="Read the content of any indexed markdown file. Use search or list_files to find paths.",
        mime_type="text/markdown",
    )
    def _file_resource(path: str) -> str:
        """Read a file from the knowledge base by its relative or absolute path."""
        from pathlib import Path as _Path

        # Support both relative (from any source root) and absolute paths
        resolved: str | None = None
        for src in settings.sources:
            candidate = _Path(src) / path
            if candidate.exists():
                resolved = str(candidate.resolve())
                break

        if resolved is None:
            abs_candidate = _Path(path)
            if abs_candidate.is_absolute() and abs_candidate.exists():
                resolved = str(abs_candidate.resolve())

        if resolved is None:
            return f"File not found: {path}"

        in_source = any(
            resolved.startswith(str(_Path(s).resolve()) + "/")
            for s in settings.sources
        )
        if not in_source:
            return "Access denied: path is outside configured sources"

        try:
            return _Path(resolved).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"Cannot read file: {exc}"


# -- Prompts -------------------------------------------------------------------

def _register_prompts(server: FastMCP, settings) -> None:
    """Register built-in MCP prompt templates."""

    @server.prompt(
        name="ask-kb",
        description="Ask a question and get an answer grounded in the knowledge base.",
    )
    def ask_kb(question: str) -> str:
        """Ask a question against the knowledge base.

        Args:
            question: The question to ask.
        """
        return (
            f"Use the `chat` tool to answer this question using the knowledge base:\n\n{question}"
        )

    @server.prompt(
        name="summarize-topic",
        description="Search the knowledge base and summarize what it says about a topic.",
    )
    def summarize_topic(topic: str) -> str:
        """Summarize knowledge-base content about a topic.

        Args:
            topic: The topic to summarize.
        """
        return (
            f"Use the `search_summarize` tool to find and summarize everything "
            f"the knowledge base contains about: {topic}"
        )

    @server.prompt(
        name="research-topic",
        description="Run deep multi-angle research on a topic using the knowledge base.",
    )
    def research_topic(topic: str) -> str:
        """Run comprehensive deep research on a topic.

        Args:
            topic: The topic to research thoroughly.
        """
        return (
            f"Use the `deep_research` tool to run thorough multi-angle research "
            f"on this topic using the knowledge base: {topic}"
        )


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

    wikidb = None
    if settings.plugin_enabled("wiki_compile"):
        from app.plugins.wiki_compile.wikidb import WikiDB
        wikidb = WikiDB(settings.data_directory)
        logger.info("WikiDB initialized for MCP (wiki_compile plugin enabled)")

    versioning_manager = None
    if settings.versioning_enabled:
        try:
            from pathlib import Path
            from app.versioning import GitManager
            versioning_manager = GitManager(Path(settings.versioning_root))
            logger.info("GitManager initialized for MCP (versioning enabled)")
        except Exception:
            logger.warning("GitManager init failed for MCP", exc_info=True)

    # Optional history tracking — record MCP calls to the web UI sidebar DBs
    chatdb = None
    searchdb = None
    if settings.mcp_enabled("track_history"):
        chatdb = ChatDB(settings.data_directory)
        searchdb = SearchDB(settings.data_directory)
        logger.info("MCP history tracking enabled (searches + chat threads)")

    # Auto-discover and register MCP tools.
    # Guard: FastMCP's streamable-HTTP session manager calls the lifespan
    # context for every new session — tools must only be registered once.
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
        "wikidb": wikidb,
        "kgdb": kgdb,
        "versioning_manager": versioning_manager,
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

def _default_allowed_hosts(bind_host: str, port: int) -> list[str]:
    """Reachable-by-default hostnames to seed the Host allowlist.

    DNS rebinding protection rejects any Host header not on the allowlist,
    which is a common cause of "Invalid Host header" 400s from legitimate
    LAN or Docker-bridge clients. We seed the list with:
      - localhost / 127.0.0.1 (always)
      - host.docker.internal (common Docker-agent bridge name)
      - the machine's hostname and ``<hostname>.local`` (mDNS)
      - the machine's LAN IPs (best-effort via socket lookup)
      - the explicit bind host when it's a specific IP

    The user can tighten this by setting ``mcp.allowed_hosts`` in
    settings.yaml, or loosen it further with ``*``.  Each entry is expanded
    to both ``name:*`` (wildcard port) and ``name:<bind-port>`` so clients
    hitting either the default MCP port or a remapped one both work.
    """
    import socket

    names: list[str] = ["localhost", "127.0.0.1", "host.docker.internal"]
    try:
        hostname = socket.gethostname()
        if hostname:
            names.append(hostname)
            names.append(f"{hostname}.local")
    except OSError:
        pass
    try:
        _, _, lan_ips = socket.gethostbyname_ex(socket.gethostname())
        names.extend(lan_ips)
    except OSError:
        pass
    if bind_host not in ("0.0.0.0", "::", "127.0.0.1", "::1", "localhost"):
        names.append(bind_host)

    entries: list[str] = []
    seen: set[str] = set()
    for name in names:
        for pattern in (f"{name}:*", f"{name}:{port}"):
            if pattern not in seen:
                seen.add(pattern)
                entries.append(pattern)
    return entries


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
        # Merge user-configured entries with the default reachable-host set.
        # User entries come first (take precedence in log/debug output).
        merged = [str(h) for h in configured_hosts]
        for h in _default_allowed_hosts(bind_host, bind_port):
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
            "MarkdownKB is a personal markdown knowledge base. Use the tools below to "
            "search indexed documents, retrieve full file contents, list indexed "
            "files, generate implementation plans, and trigger re-indexing."
        ),
        lifespan=lifespan,
        transport_security=transport_security,
    )

    # Resources and prompts are static — register at creation time so they
    # are available immediately, not deferred to the first lifespan call.
    _register_resources(mcp, settings)
    _register_prompts(mcp, settings)

    return mcp


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
                    level = 60 if level_str == "OFF" else getattr(logging, level_str, logging.INFO)
                    logging.getLogger().setLevel(level)
                    if level_str != "OFF":
                        logger.info("MCP log level changed to %s", level_str)
                    response = JSONResponse({"level": level_str})
                else:
                    current = logging.getLogger().level
                    level_name = "OFF" if current >= 60 else logging.getLevelName(current)
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

    mcp = _create_mcp(bind_host=args.host, bind_port=args.port)

    if args.http:
        logger.info("Starting MCP server (Streamable HTTP) on %s:%d", args.host, args.port)
        _run_http_with_auth(mcp, args.host, args.port)
    else:
        logger.info("Starting MCP server (stdio)")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
