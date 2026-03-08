"""Graph endpoints for knowledge graph visualization."""

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import Settings
from app.deps import get_retriever, get_scopedb, get_settings
from app.events import event_bus
from app.rag.retriever import Retriever
from app.ratelimit import STANDARD, limiter
from app.services.graph_service import compute_graph
from app.storage.scopedb import ScopeDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])

# In-memory cache: key = (frozenset(source_roots), top_k) -> graph data
_graph_cache: dict[tuple, dict] = {}
_cache_lock = threading.Lock()


def _resolve_scope(scope_id: str | None, scopedb: ScopeDB) -> list[str] | None:
    if not scope_id:
        return None
    scope = scopedb.get(scope_id)
    if not scope:
        raise HTTPException(status_code=404, detail="Scope not found")
    return scope["folders"]


def _cache_key(source_roots: list[str] | None, top_k: int) -> tuple:
    roots = frozenset(source_roots) if source_roots else frozenset()
    return (roots, top_k)


@router.get("/data")
@limiter.limit(STANDARD)
def graph_data(
    request: Request,
    scope_id: str | None = None,
    top_k: int = 3,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    scopedb: ScopeDB = Depends(get_scopedb),
):
    """Return the full knowledge graph (nodes, edges, clusters, word clouds)."""
    scope_folders = _resolve_scope(scope_id, scopedb)
    key = _cache_key(scope_folders, top_k)

    with _cache_lock:
        if key in _graph_cache:
            return _graph_cache[key]

    result = compute_graph(retriever.store, scope_folders, top_k)

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
