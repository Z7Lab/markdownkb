"""Main application entry point — FastAPI backend with static frontend."""

import logging
import threading
from pathlib import Path

import uvicorn
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import create_api
from app.config import Settings
from app.ingestion.indexer import run_index
from app.ingestion.watcher import start_watching
from app.rag.retriever import Retriever
from app.storage.chatdb import ChatDB
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def _start_watcher(
    settings: Settings, store: VectorStore,
    tracking: TrackingDB,
):
    """Start the file watcher daemon thread."""
    thread = threading.Thread(
        target=start_watching,
        args=(settings, store, tracking),
        daemon=True,
    )
    thread.start()
    logger.info("File watcher started")


def main():
    """Start the mdkb server."""
    settings = Settings.get()

    store = VectorStore(
        settings.persist_directory, settings.collection_name,
    )
    tracking = TrackingDB(settings.data_directory)
    chatdb = ChatDB(settings.data_directory)

    if store.count == 0:
        logger.info("Empty store, running initial index...")
        run_index(settings, store, tracking)

    retriever = Retriever(store, settings)
    cancel_event = threading.Event()

    app = create_api(
        settings, store, retriever, tracking, chatdb, cancel_event,
    )

    # Serve frontend static files in production
    if FRONTEND_DIR.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=FRONTEND_DIR / "assets"),
            name="assets",
        )

        @app.get("/{path:path}")
        async def spa_fallback(request: Request, path: str):
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

    if settings.feature_enabled("file_watcher"):
        _start_watcher(settings, store, tracking)

    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
    )


if __name__ == "__main__":
    main()
