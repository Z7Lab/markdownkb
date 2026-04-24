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
from app.logging_ctx import install_request_id_log_factory
from app.config import Settings
from app.embeddings.downloader import is_installed
from app.embeddings.registry import load_models
from app.logbuffer import log_buffer
from app.ratelimit import limiter
from app.ingestion.indexer import run_index
from app.ingestion.watcher import FileWatcher
from app.rag.retriever import Retriever
from app.storage.chatdb import ChatDB
from app.storage.plandb import PlanDB
from app.storage.searchdb import SearchDB
from app.storage.presetsdb import PresetsDB
from app.storage.scopedb import ScopeDB
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

# LogRecord factory must be installed BEFORE basicConfig so the root
# handler's first records already carry the request_id attribute.
install_request_id_log_factory()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [rid=%(request_id)s] %(name)s: %(message)s",
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
    presetsdb = PresetsDB(settings.data_directory)

    # Validate configured source paths — warn early rather than silently missing files
    for src in settings.sources:
        if not Path(src).exists():
            logger.warning(
                "Configured source path does not exist: %s — files will not be indexed",
                src,
            )

    # Load embedding model registry from config
    load_models(settings.model_configs)

    # Check embedding model — don't auto-download, let the user choose
    model_id = settings.embedding_model
    if not is_installed(model_id):
        logger.warning(
            "Embedding model '%s' not installed — indexing and search disabled. "
            "Go to Settings > Embedding Model to download one.",
            model_id,
        )
        app.state.embedding_model_missing = True
    else:
        app.state.embedding_model_missing = False

    # Regenerate compose.override.yml from current config so Docker volume
    # mounts always reflect settings.yaml sources and project roots.
    from app.config.docker import write_compose_override
    try:
        project_root = settings.project_root
        all_configs = (
            settings.source_configs
            + settings.project_root_source_configs
            + settings.bucket_mount_configs
        )
        write_compose_override(all_configs, project_root)
    except Exception:
        logger.debug("Could not sync compose.override.yml on startup", exc_info=True)

    # Reset files stuck in "indexing" from a previous interrupted run
    reset_count = tracking.reset_incomplete()
    if reset_count:
        logger.info("Reset %d files stuck in 'indexing' from interrupted run", reset_count)

    retriever = Retriever(store, settings, tracking)
    cancel_event = threading.Event()

    if store.count == 0 and tracking.file_count() > 0:
        # ChromaDB empty but tracking has records (collection rename,
        # model switch, or interrupted startup) — clear stale records
        # so every file is re-scanned.
        logger.info("ChromaDB empty but tracking has %d files — clearing stale records", tracking.file_count())
        tracking.clear()

    # Always run the indexer on startup — it skips unchanged files (hash
    # comparison) so this is fast when everything is up to date. This
    # catches files added between restarts that the watcher never saw.
    from app.services.task_registry import get_default_registry, run_tracked
    logger.info("Starting background index scan...")
    run_tracked(
        kind="startup_index",
        target=lambda: run_index(settings, store, tracking, cancel=cancel_event),
        label="Startup index scan",
        registry=get_default_registry(),
    )

    # Initialise versioning manager (git-backed revision history).
    # Failure is non-fatal — writers fall back to unversioned behaviour.
    versioning_manager = None
    if settings.versioning_enabled:
        try:
            from app.versioning import GitManager
            versioning_manager = GitManager(Path(settings.versioning_root))
            for cfg in settings.source_configs:
                if cfg.get("versioned") and Path(cfg["path"]).is_dir():
                    try:
                        versioning_manager.ensure_repo(cfg["path"])
                    except Exception:
                        logger.warning(
                            "versioning: could not initialise repo for %s",
                            cfg["path"], exc_info=True,
                        )
            logger.info("Versioning manager initialised at %s", settings.versioning_root)
        except Exception:
            logger.warning("Versioning manager failed to initialise", exc_info=True)
            versioning_manager = None

    # Store services on app.state for dependency injection
    from app.services.chat_service import ConversationHistory
    from app.services.task_registry import get_default_registry
    app.state.settings = settings
    app.state.using_default_config = settings.using_defaults
    app.state.store = store
    app.state.retriever = retriever
    app.state.tracking = tracking
    app.state.chatdb = chatdb
    app.state.searchdb = searchdb
    app.state.plandb = plandb
    app.state.scopedb = scopedb
    app.state.presetsdb = presetsdb
    app.state.cancel_event = cancel_event
    app.state.conversation_history = ConversationHistory()
    app.state.versioning_manager = versioning_manager
    app.state.task_registry = get_default_registry()

    # Initialize plugin resources (on_startup hooks)
    from app.plugins import init_plugins
    init_plugins(app)

    # Restore persisted log level
    log_level = getattr(logging, settings.log_level, logging.INFO)
    logging.getLogger().setLevel(log_level)

    # Rate limiting: explicit opt-in via core flag, or auto-enabled when the
    # server binds to a non-localhost address (0.0.0.0 / :: / explicit LAN IP).
    # Auto-enable ensures network-exposed deployments have brute-force / cost
    # protection on by default without relying on user configuration.
    bind_host = settings.server_host
    network_exposed = bind_host not in ("127.0.0.1", "::1", "localhost")
    if settings.core_enabled("rate_limiting"):
        limiter.enabled = True
        logger.info("Rate limiting enabled (core flag)")
    elif network_exposed:
        limiter.enabled = True
        logger.warning(
            "Rate limiting auto-enabled: server is binding to %s (network-exposed).",
            bind_host,
        )

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

    # Shutdown: signal background threads to stop before closing DBs
    if hasattr(app.state, "cancel_event"):
        app.state.cancel_event.set()

    # Shutdown: close DB connections
    tracking.close()
    chatdb.close()
    searchdb.close()
    plandb.close()
    scopedb.close()
    presetsdb.close()
    logger.info("Shutdown complete")


def main():
    """Start the MarkdownKB server."""
    settings = Settings.get()
    app = create_app(lifespan=lifespan)

    # Serve frontend static files in production
    if FRONTEND_DIR.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=FRONTEND_DIR / "assets"),
            name="assets",
        )

        # IMPORTANT: this catch-all must be registered LAST — after all
        # include_router() calls in create_app() — so it does not shadow
        # API or plugin routes.  create_app() includes all routers before
        # returning, and main() registers this route after that call.
        @app.get("/{path:path}")
        async def spa_fallback(_request: Request, path: str):
            """Serve index.html for all non-API routes (SPA routing)."""
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            file_path = (FRONTEND_DIR / path).resolve()
            try:
                file_path.relative_to(FRONTEND_DIR.resolve())
            except ValueError:
                return JSONResponse({"detail": "Not Found"}, status_code=404)
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
