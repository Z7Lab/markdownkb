"""FastAPI application factory."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.ratelimit import limiter
from app.routers import (
    chat,
    embeddings,
    export,
    files,
    health,
    search,
    settings,
    tags,
    threads,
)


def create_app(lifespan=None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="mdkb API", version="1.0.0", lifespan=lifespan)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            f"http://localhost:{os.environ.get('FRONTEND_PORT', '9714')}",
        ],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )

    # Core routers
    for router_module in (
        health, search, chat, threads, files,
        settings, embeddings, export,
    ):
        app.include_router(router_module.router)

    # Conditionally register tags router if feature is enabled
    from app.config import Settings
    settings_instance = Settings.get()
    if settings_instance.feature_enabled("mcp_tag_generator"):
        app.include_router(tags.router)

    return app
