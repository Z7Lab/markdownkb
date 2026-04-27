"""FastAPI application factory."""

import logging
import os
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.logging_ctx import request_id_var
from app.ratelimit import limiter

_access_logger = logging.getLogger("app.access")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Propagate or mint an X-Request-ID header for every request.

    Stores the id in a ContextVar so any logger called during handler
    execution (including in the default threadpool for sync routes) can
    attach it to log records via ``RequestIdFilter``. Echoes the id back
    on the response so clients can cross-reference server logs.
    """

    _HEADER = "X-Request-ID"

    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get(self._HEADER, "").strip()
        # Cap length to prevent log-injection via oversized client ids.
        rid = incoming[:64] if incoming else uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[self._HEADER] = rid
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            _access_logger.exception(
                "%s %s -> 500 (%.1fms)",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if request.url.path != "/api/v1/settings/logs":
            _access_logger.info(
                "%s %s -> %s (%.1fms)",
                request.method,
                request.url.path,
                status,
                elapsed_ms,
            )
        return response


def _register_exception_handlers(app: FastAPI) -> None:
    """Register a catch-all handler so unhandled errors return a generic 500.

    Without this, enabling ``debug=True`` at any point would leak tracebacks
    to clients. The handler logs the exception for debugging and returns a
    stable, minimal body shape.
    """
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    handler_log = logging.getLogger("app.errors")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):  # pragma: no cover - defensive
        if isinstance(exc, (StarletteHTTPException, RequestValidationError, RateLimitExceeded)):
            raise exc
        handler_log.exception(
            "Unhandled error on %s %s: %s",
            request.method, request.url.path, exc.__class__.__name__,
        )
        return JSONResponse({"detail": "Internal server error"}, status_code=500)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "frame-ancestors 'none'"
        )
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response


from app.routers import (
    chat,
    dashboard,
    embeddings,
    files,
    health,
    llm,
    maintenance,
    mcp,
    plugins,
    scopes,
    settings,
    setup,
    sources,
    tasks,
    threads,
)
from app.versioning.router import router as versioning_router
from app.backups.router import router as backups_router
from app.routers.export_md import router as export_md_router
from app.version_check.router import router as version_check_router


def create_app(lifespan=None, settings_override=None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        lifespan: ASGI lifespan context manager.
        settings_override: Optional settings object for testing.  When
            provided, plugin registration uses this instead of the global
            singleton.
    """
    from app.version import APP_VERSION
    app = FastAPI(title="MarkdownKB API", version=APP_VERSION, lifespan=lifespan)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    # RequestIdMiddleware is added last so it becomes the outermost layer:
    # the id is set before any other middleware runs and the response header
    # is attached after they all return.
    app.add_middleware(RequestIdMiddleware)

    # Resolve settings early for CORS config
    from app.config import Settings
    cfg = settings_override if settings_override is not None else Settings.get()

    # Core routers (always registered)
    for router_module in (
        health, chat, threads, files,
        settings, setup, sources, llm, maintenance,
        embeddings, scopes, plugins, mcp, tasks,
        dashboard,
    ):
        app.include_router(router_module.router)
    app.include_router(versioning_router)
    app.include_router(backups_router)
    app.include_router(export_md_router)
    app.include_router(version_check_router)

    # Auto-discover and register plugins (feature-gated)
    from app.plugins import register_plugins
    register_plugins(app, cfg)

    # API key authentication
    api_key = getattr(cfg, "api_key", "")
    bind_host = getattr(cfg, "server_host", "127.0.0.1")
    network_exposed = bind_host in ("0.0.0.0", "::")

    # Auth middleware is added before CORS so that CORS (added last, outermost)
    # wraps auth rejections and applies Access-Control-Allow-Origin headers
    # even on 401 responses. This lets browser clients see the real 401 instead
    # of a masked CORS error. The middleware reads app.state.api_key on each
    # request, so the key can be set or changed at runtime without rebuilding
    # the stack.
    from app.auth import ApiKeyMiddleware
    app.add_middleware(ApiKeyMiddleware)

    # Register a catch-all exception handler so unhandled errors return a
    # generic 500 body without leaking tracebacks, while still being logged
    # for later investigation.
    _register_exception_handlers(app)

    # CORS must be the outermost user middleware so rejected auth responses
    # still receive CORS headers. add_middleware prepends internally, so the
    # last-added middleware becomes the outermost layer.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=getattr(cfg, "cors_origins", [f"http://localhost:{os.environ.get('FRONTEND_PORT', '9714')}"]),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "X-MarkdownKB-Key"],
    )

    app.state.api_key = api_key

    if api_key:
        app.state.auth_enabled = True
    else:
        app.state.auth_enabled = False
        if network_exposed:
            logging.getLogger(__name__).warning(
                "Server binding to %s without API key authentication. "
                "Open the web UI to generate a key, or set MARKDOWNKB_API_KEY.",
                bind_host,
            )
        else:
            logging.getLogger(__name__).info(
                "API key authentication disabled (localhost-only binding on %s).",
                bind_host,
            )
    app.state.network_exposed = network_exposed

    return app
