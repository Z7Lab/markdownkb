"""Graph endpoints for knowledge graph visualization."""

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import Settings
from app.deps import get_retriever, get_scopedb, get_settings
from app.events import event_bus
from app.rag.retriever import Retriever
from app.ratelimit import STANDARD, limiter
from app.services.graph_service import compute_edge_detail, compute_graph, graph_progress
from app.storage.scopedb import ScopeDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])

# In-memory cache: key = (frozenset(source_roots), top_k) -> graph data
_graph_cache: dict[tuple, dict] = {}
_cache_lock = threading.Lock()


def _resolve_scope(scope_id: str | None, scopedb: ScopeDB) -> list[str] | None:
    """Resolve scope to folder list. Graph only supports folder-based filtering."""
    if not scope_id:
        return None
    scope = scopedb.get(scope_id)
    if not scope:
        raise HTTPException(status_code=404, detail="Scope not found")
    return scope["folders"] or None


def _cache_key(source_roots: list[str] | None, top_k: int, word_clouds: bool = True, min_weight: float = 0.0) -> tuple:
    roots = frozenset(source_roots) if source_roots else frozenset()
    return (roots, top_k, word_clouds, min_weight)


@router.get("/data")
@limiter.limit(STANDARD)
def graph_data(
    request: Request,
    scope_id: str | None = None,
    top_k: int = 3,
    word_clouds: bool = True,
    min_weight: float = 0.5,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    scopedb: ScopeDB = Depends(get_scopedb),
):
    """Return the full knowledge graph (nodes, edges, clusters, word clouds)."""
    scope_folders = _resolve_scope(scope_id, scopedb)
    key = _cache_key(scope_folders, top_k, word_clouds, min_weight)

    with _cache_lock:
        if key in _graph_cache:
            return _graph_cache[key]

    result = compute_graph(
        retriever.store, scope_folders, top_k,
        word_clouds=word_clouds, min_weight=min_weight,
    )

    with _cache_lock:
        _graph_cache[key] = result

    return result


@router.get("/stats")
@limiter.limit(STANDARD)
def graph_stats(
    request: Request,
    scope_id: str | None = None,
    retriever: Retriever = Depends(get_retriever),
    scopedb: ScopeDB = Depends(get_scopedb),
):
    """Lightweight stats without computing the full graph."""
    scope_folders = _resolve_scope(scope_id, scopedb)

    if scope_folders:
        raw = retriever.store.get_all_with_embeddings(scope_folders)
        all_meta = raw["metadatas"]
    else:
        all_meta = retriever.store.get_all_metadatas()

    doc_paths = set()
    for m in all_meta:
        doc_paths.add(m.get("source_path", ""))

    return {
        "doc_count": len(doc_paths),
        "chunk_count": len(all_meta),
    }


@router.get("/status")
@limiter.limit(STANDARD)
def graph_status(
    request: Request,
    scope_id: str | None = None,
    top_k: int = 3,
    word_clouds: bool = True,
    min_weight: float = 0.5,
    scopedb: ScopeDB = Depends(get_scopedb),
):
    """Check if cached graph data is available (no computation)."""
    scope_folders = _resolve_scope(scope_id, scopedb)
    key = _cache_key(scope_folders, top_k, word_clouds, min_weight)
    with _cache_lock:
        return {"cached": key in _graph_cache}


@router.get("/edge-detail")
@limiter.limit(STANDARD)
def edge_detail(
    request: Request,
    source: str = "",
    target: str = "",
    top_k: int = 5,
    retriever: Retriever = Depends(get_retriever),
):
    """Return chunk-level similarity detail for a single document pair."""
    if not source or not target:
        raise HTTPException(status_code=400, detail="source and target are required")
    return compute_edge_detail(retriever.store, source, target, top_k)


@router.get("/progress")
@limiter.limit(STANDARD)
def get_graph_progress(request: Request):
    """Return current graph computation progress."""
    return {
        "fraction": graph_progress["fraction"],
        "phase": graph_progress["phase"],
    }


# Cache invalidation via IndexEventBus
def _invalidation_worker():
    q = event_bus.subscribe()
    while True:
        event = q.get()
        if event is None:
            break
        if event.type in ("indexed", "deleted"):
            with _cache_lock:
                _graph_cache.clear()
            logger.debug("Graph cache cleared due to %s event", event.type)


_invalidation_thread = threading.Thread(
    target=_invalidation_worker, daemon=True, name="graph-cache-invalidation",
)
_invalidation_thread.start()
