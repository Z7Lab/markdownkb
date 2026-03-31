"""FastAPI application factory."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.ratelimit import limiter


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


from app.routers import (
    chat,
    embeddings,
    files,
    health,
    llm,
    maintenance,
    plugins,
    scopes,
    settings,
    setup,
    sources,
    threads,
)


def create_app(lifespan=None, settings_override=None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        lifespan: ASGI lifespan context manager.
        settings_override: Optional settings object for testing.  When
            provided, plugin registration uses this instead of the global
            singleton.
    """
    app = FastAPI(title="mdkb API", version="1.0.0", lifespan=lifespan)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(SecurityHeadersMiddleware)

    # Resolve settings early for CORS config
    from app.config import Settings
    cfg = settings_override if settings_override is not None else Settings.get()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=getattr(cfg, "cors_origins", [f"http://localhost:{os.environ.get('FRONTEND_PORT', '9714')}"]),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "X-MDKB-Key"],
    )

    # Core routers (always registered)
    for router_module in (
        health, chat, threads, files,
        settings, setup, sources, llm, maintenance,
        embeddings, scopes, plugins,
    ):
        app.include_router(router_module.router)

    # Auto-discover and register plugins (feature-gated)
    from app.plugins import register_plugins
    register_plugins(app, cfg)

    # API key authentication
    import logging
    api_key = getattr(cfg, "api_key", "")
    bind_host = os.environ.get("SERVER_HOST", os.environ.get("HOST", os.environ.get("UVICORN_HOST", "127.0.0.1")))
    network_exposed = bind_host in ("0.0.0.0", "::")

    if api_key:
        from app.auth import ApiKeyMiddleware
        app.add_middleware(ApiKeyMiddleware, api_key=api_key)
        app.state.auth_enabled = True
    else:
        app.state.auth_enabled = False
        if network_exposed:
            logging.getLogger(__name__).warning(
                "Server binding to %s without API key authentication. "
                "Open the web UI to generate a key, or set MDKB_API_KEY.",
                bind_host,
            )
        else:
            logging.getLogger(__name__).info(
                "API key authentication disabled (localhost-only binding on %s).",
                bind_host,
            )
    app.state.network_exposed = network_exposed

    return app
