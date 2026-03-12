"""FastAPI application factory."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.ratelimit import limiter
from app.routers import (
    chat,
    embeddings,
    files,
    health,
    plugins,
    scopes,
    settings,
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
        settings, embeddings, scopes, plugins,
    ):
        app.include_router(router_module.router)

    # Auto-discover and register plugins (feature-gated)
    from app.plugins import register_plugins
    register_plugins(app, cfg)

    # API key authentication (only when a key is configured)
    api_key = getattr(cfg, "api_key", "")
    if api_key:
        from app.auth import ApiKeyMiddleware
        app.add_middleware(ApiKeyMiddleware, api_key=api_key)
    else:
        import logging
        bind_host = os.environ.get("HOST", os.environ.get("UVICORN_HOST", "127.0.0.1"))
        if bind_host in ("0.0.0.0", "::"):
            logging.getLogger(__name__).warning(
                "Server binding to %s without API key authentication. "
                "Set auth.api_key in settings or MDKB_API_KEY env var to secure the API.",
                bind_host,
            )

    return app
