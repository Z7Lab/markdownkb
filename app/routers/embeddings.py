"""Embedding model management and indexing endpoints."""

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.config import Settings
from app.deps import get_cancel_event, get_settings, get_store, get_tracking
from app.embeddings.downloader import (
    install_from_local,
    install_model,
    is_installed,
    list_models_with_status,
    uninstall_model,
)
from app.embeddings.embedder import unload_model
from app.embeddings.registry import MODELS
from app.ingestion.indexer import run_index
from app.ratelimit import INDEXING, STANDARD, limiter
from app.schemas.embeddings import EmbeddingModelRequest, IndexRequest
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["embeddings"])

# Background reindex state — module-level because only one reindex can
# run at a time across the process.  Guarded by _switch_lock.
_switch_status: dict = {
    "running": False,
    "progress": 0.0,
    "message": "",
    "result": "",
}
_switch_lock = threading.Lock()


def reset_switch_status() -> None:
    """Reset background operation state (used in tests to prevent state leakage)."""
    with _switch_lock:
        _switch_status["running"] = False
        _switch_status["progress"] = 0.0
        _switch_status["message"] = ""
        _switch_status["result"] = ""


def _bg_reindex(
    settings: Settings,
    store: VectorStore,
    tracking: TrackingDB,
    cancel_event: threading.Event,
):
    """Run reindex in background thread, updating _switch_status."""
    def on_progress(frac: float, msg: str):
        with _switch_lock:
            _switch_status["progress"] = frac
            _switch_status["message"] = msg

    try:
        cancel_event.clear()
        result = run_index(
            settings, store, tracking,
            progress=on_progress,
            cancel=cancel_event,
        )
        with _switch_lock:
            _switch_status["result"] = result
    except (OSError, RuntimeError, ValueError) as e:
        logger.error("Background reindex failed: %s", e)
        with _switch_lock:
            _switch_status["result"] = f"Error: {e}"
    finally:
        with _switch_lock:
            _switch_status["running"] = False


@router.get("/settings/embedding-models")
@limiter.limit(STANDARD)
def list_embedding_models(request: Request, settings: Settings = Depends(get_settings)):
    """List available embedding models with installation status."""
    return {
        "models": list_models_with_status(),
        "active_model": settings.embedding_model,
        "provider": settings.embedding_provider,
        "remote_config": settings.embedding_remote_config,
    }


class _RemoteEmbeddingTestRequest(BaseModel):
    model: str = "nomic-embed-text"
    api_base: str
    api_type: str = "ollama"
    api_key: str = ""


class _EmbeddingProviderRequest(BaseModel):
    provider: str  # "local" or "remote"
    remote_model: str = "nomic-embed-text"
    api_base: str = ""
    api_type: str = "ollama"
    api_key: str = ""


@router.post("/settings/embedding-models/test-remote")
@limiter.limit(STANDARD)
def test_remote_embedding_endpoint(request: Request, req: _RemoteEmbeddingTestRequest):
    """Test a remote embedding endpoint."""
    from app.embeddings.remote import test_remote_embedding
    return test_remote_embedding(req.model, req.api_base, req.api_type, api_key=req.api_key)


@router.put("/settings/embedding-provider")
@limiter.limit(STANDARD)
def save_embedding_provider(
    request: Request,
    req: _EmbeddingProviderRequest,
    settings: Settings = Depends(get_settings),
):
    """Save embedding provider config (local or remote)."""
    settings.embedding_provider = req.provider
    settings.update_embedding_remote_config(req.api_base, req.remote_model, req.api_type)
    settings.save()
    return {"status": "saved", "provider": req.provider}


@router.get("/settings/embedding-models/status")
@limiter.limit(STANDARD)
def embedding_switch_status(request: Request):
    """Return current background reindex progress."""
    with _switch_lock:
        return dict(_switch_status)


def _bg_install(model_id: str, app_state=None):
    """Install embedding model in background thread, updating _switch_status."""
    def on_progress(frac: float, msg: str):
        with _switch_lock:
            _switch_status["progress"] = frac
            _switch_status["message"] = msg

    try:
        info = MODELS[model_id]
        if info.local_path:
            install_from_local(model_id, info.local_path, progress=on_progress)
        else:
            install_model(model_id, progress=on_progress)
        with _switch_lock:
            _switch_status["result"] = f"Installed {model_id}"
        # Clear the missing flag so the banner disappears
        if app_state:
            app_state.embedding_model_missing = False
    except (OSError, RuntimeError, ValueError) as e:
        logger.error("Failed to install embedding model %s: %s", model_id, e)
        with _switch_lock:
            _switch_status["result"] = f"Error: {e}"
    finally:
        with _switch_lock:
            _switch_status["running"] = False


@router.post("/settings/embedding-models/install")
@limiter.limit(INDEXING)
def install_embedding_model_endpoint(request: Request, req: EmbeddingModelRequest):
    """Download an embedding model in the background."""
    if req.model_id not in MODELS:
        raise HTTPException(400, f"Unknown model: {req.model_id}")
    if is_installed(req.model_id):
        return {"status": "already_installed"}

    with _switch_lock:
        if _switch_status["running"]:
            raise HTTPException(409, "An install or reindex operation is already in progress")
        _switch_status["running"] = True
        _switch_status["progress"] = 0.0
        _switch_status["message"] = f"Starting install of {req.model_id}..."
        _switch_status["result"] = ""

    threading.Thread(target=_bg_install, args=(req.model_id, request.app.state), daemon=True).start()
    return {"status": "installing"}


@router.post("/settings/embedding-models/uninstall")
@limiter.limit(STANDARD)
def uninstall_embedding_model(
    request: Request,
    req: EmbeddingModelRequest,
    settings: Settings = Depends(get_settings),
):
    """Remove a downloaded embedding model from disk."""
    if req.model_id not in MODELS:
        raise HTTPException(400, f"Unknown model: {req.model_id}")
    if req.model_id == settings.embedding_model:
        raise HTTPException(400, "Cannot uninstall the active model")
    with _switch_lock:
        if _switch_status["running"]:
            raise HTTPException(409, "An operation is already in progress")
    if not is_installed(req.model_id):
        return {"status": "not_installed"}
    uninstall_model(req.model_id)
    return {"status": "removed"}


@router.put("/settings/embedding-models/switch")
@limiter.limit(INDEXING)
def switch_embedding_model(
    request: Request,
    req: EmbeddingModelRequest,
    settings: Settings = Depends(get_settings),
    store: VectorStore = Depends(get_store),
    tracking: TrackingDB = Depends(get_tracking),
    cancel_event: threading.Event = Depends(get_cancel_event),
):
    """Switch active embedding model, clearing vectors and reindexing."""
    if req.model_id not in MODELS:
        raise HTTPException(400, f"Unknown model: {req.model_id}")
    if not is_installed(req.model_id):
        raise HTTPException(400, f"Model not installed: {req.model_id}")
    if req.model_id == settings.embedding_model:
        return {"status": "already_active"}

    with _switch_lock:
        if _switch_status["running"]:
            raise HTTPException(409, "A reindex operation is already in progress")
        _switch_status["running"] = True
        _switch_status["progress"] = 0.0
        _switch_status["message"] = "Preparing to switch..."
        _switch_status["result"] = ""

        logger.info("Switching embedding model from %s to %s", settings.embedding_model, req.model_id)
        settings.embedding_model = req.model_id
        settings.save()
        unload_model()
        store.clear()
        tracking.clear()

        threading.Thread(
            target=_bg_reindex,
            args=(settings, store, tracking, cancel_event),
            daemon=True,
        ).start()
    return {"status": "switching", "model": req.model_id}


# -- Indexing --

@router.post("/index")
@limiter.limit(INDEXING)
def index(
    request: Request,
    req: IndexRequest = IndexRequest(),
    settings: Settings = Depends(get_settings),
    store: VectorStore = Depends(get_store),
    tracking: TrackingDB = Depends(get_tracking),
    cancel_event: threading.Event = Depends(get_cancel_event),
):
    """Run indexing. With force=true, clears hashes and reindexes everything."""
    if settings.embedding_provider == "local":
        model_info = MODELS.get(settings.embedding_model)
        if model_info:
            stored_dims = store.get_stored_dimensions()
            if stored_dims is not None and stored_dims != model_info.dimensions:
                raise HTTPException(
                    409,
                    f"Vector dimension mismatch: the stored vectors are {stored_dims}-dimensional "
                    f"(from a previous model), but '{settings.embedding_model}' produces "
                    f"{model_info.dimensions}-dimensional vectors. "
                    f"Go to Settings → Database and clear the vector store before indexing.",
                )

    if req.force:
        with _switch_lock:
            if _switch_status["running"]:
                raise HTTPException(409, "A reindex operation is already in progress")
            _switch_status["running"] = True
            _switch_status["progress"] = 0.0
            _switch_status["message"] = "Preparing force reindex..."
            _switch_status["result"] = ""

        tracking.clear_hashes()

        threading.Thread(
            target=_bg_reindex,
            args=(settings, store, tracking, cancel_event),
            daemon=True,
        ).start()
        return {"status": "reindexing"}

    cancel_event.clear()

    def _run_index_safe():
        try:
            run_index(settings, store, tracking, cancel=cancel_event)
        except Exception:
            logger.error("Background index failed", exc_info=True)

    threading.Thread(target=_run_index_safe, daemon=True).start()
    return {"status": "indexing", "message": "Indexing started in background"}


@router.post("/index/cancel")
@limiter.limit(STANDARD)
def cancel_index(request: Request, cancel_event: threading.Event = Depends(get_cancel_event)):
    """Cancel a running index operation."""
    cancel_event.set()
    return {"status": "cancelling"}
