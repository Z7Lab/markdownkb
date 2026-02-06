"""Main application entry point — FastAPI backend with static frontend."""

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import create_app
from app.config import Settings
from app.ratelimit import limiter
from app.ingestion.indexer import run_index
from app.ingestion.watcher import start_watching
from app.rag.retriever import Retriever
from app.storage.chatdb import ChatDB
from app.storage.searchdb import SearchDB
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, clean up on shutdown."""
    settings = Settings.get()

    store = VectorStore(
        settings.persist_directory, settings.collection_name,
    )
    tracking = TrackingDB(settings.data_directory)
    chatdb = ChatDB(settings.data_directory)
    searchdb = SearchDB(settings.data_directory)

    if store.count == 0:
        logger.info("Empty store, running initial index...")
        run_index(settings, store, tracking)

    retriever = Retriever(store, settings, tracking)
    cancel_event = threading.Event()

    # Store services on app.state for dependency injection
    app.state.settings = settings
    app.state.store = store
    app.state.retriever = retriever
    app.state.tracking = tracking
    app.state.chatdb = chatdb
    app.state.searchdb = searchdb
    app.state.cancel_event = cancel_event

    # Enable rate limiting if configured
    if settings.feature_enabled("rate_limiting"):
        limiter.enabled = True
        logger.info("Rate limiting enabled")

    # Start file watcher if enabled
    if settings.feature_enabled("file_watcher"):
        thread = threading.Thread(
            target=start_watching,
            args=(settings, store, tracking),
            daemon=True,
        )
        thread.start()
        logger.info("File watcher started")

    yield

    # Shutdown: close DB connections
    tracking.close()
    chatdb.close()
    searchdb.close()
    logger.info("Shutdown complete")


def main():
    """Start the mdkb server."""
    settings = Settings.get()
    app = create_app(lifespan=lifespan)

    # Serve frontend static files in production
    if FRONTEND_DIR.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=FRONTEND_DIR / "assets"),
            name="assets",
        )

        @app.get("/{path:path}")
        async def spa_fallback(_request: Request, path: str):
            """Serve index.html for all non-API routes (SPA routing)."""
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            file_path = FRONTEND_DIR / path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(FRONTEND_DIR / "index.html")
    else:
        logger.warning(
            "Frontend not built (%s missing). "
            "Run: cd frontend && npm run build",
            FRONTEND_DIR,
        )

    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
    )


if __name__ == "__main__":
    main()
