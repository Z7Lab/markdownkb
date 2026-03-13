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
from app.embeddings.downloader import install_from_local, install_model, is_installed
from app.embeddings.registry import MODELS, load_models
from app.logbuffer import log_buffer
from app.ratelimit import limiter
from app.ingestion.indexer import run_index
from app.ingestion.watcher import FileWatcher
from app.rag.retriever import Retriever
from app.storage.chatdb import ChatDB
from app.storage.plandb import PlanDB
from app.storage.searchdb import SearchDB
from app.storage.scopedb import ScopeDB
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger().addHandler(log_buffer)
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
    plandb = PlanDB(settings.data_directory)
    scopedb = ScopeDB(settings.data_directory)

    # Load embedding model registry from config
    load_models(settings.model_configs)

    # Auto-install the configured embedding model on first run
    model_id = settings.embedding_model
    if not is_installed(model_id):
        model_info = MODELS.get(model_id)
        local_path = model_info.local_path if model_info else ""
        try:
            if local_path:
                logger.info("Installing embedding model '%s' from local path: %s", model_id, local_path)
                install_from_local(model_id, local_path)
            else:
                logger.info("Embedding model '%s' not found, downloading...", model_id)
                install_model(model_id)
            logger.info("Embedding model '%s' installed", model_id)
        except Exception:
            logger.exception("Failed to install embedding model '%s' — indexing will fail until it is installed", model_id)

    # Reset files stuck in "indexing" from a previous interrupted run
    reset_count = tracking.reset_incomplete()
    if reset_count:
        logger.info("Reset %d files stuck in 'indexing' from interrupted run", reset_count)

    retriever = Retriever(store, settings, tracking)
    cancel_event = threading.Event()

    if store.count == 0:
        logger.info("Empty store, starting initial index in background...")
        threading.Thread(
            target=run_index,
            args=(settings, store, tracking),
            kwargs={"cancel": cancel_event},
            daemon=True,
        ).start()

    # Store services on app.state for dependency injection
    from app.services.chat_service import ConversationHistory
    app.state.settings = settings
    app.state.store = store
    app.state.retriever = retriever
    app.state.tracking = tracking
    app.state.chatdb = chatdb
    app.state.searchdb = searchdb
    app.state.plandb = plandb
    app.state.scopedb = scopedb
    app.state.cancel_event = cancel_event
    app.state.conversation_history = ConversationHistory()

    # Initialize plugin resources (on_startup hooks)
    from app.plugins import init_plugins
    init_plugins(app)

    # Restore persisted log level
    log_level = getattr(logging, settings.log_level, logging.INFO)
    logging.getLogger().setLevel(log_level)

    # Enable rate limiting if configured
    if settings.core_enabled("rate_limiting"):
        limiter.enabled = True
        logger.info("Rate limiting enabled")

    # Start file watcher if enabled
    app.state.watcher = None
    if settings.core_enabled("file_watcher"):
        watcher = FileWatcher(settings, store, tracking)
        watcher.start()
        app.state.watcher = watcher
        logger.info("File watcher started")

    yield

    # Shutdown: stop file watcher
    if app.state.watcher is not None:
        app.state.watcher.stop()
        logger.info("File watcher stopped")

    # Shutdown: plugin cleanup (before core DBs close)
    from app.plugins import shutdown_plugins
    shutdown_plugins(app)

    # Shutdown: close DB connections
    tracking.close()
    chatdb.close()
    searchdb.close()
    plandb.close()
    scopedb.close()
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
