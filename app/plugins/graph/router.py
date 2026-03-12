"""Graph endpoints for knowledge graph visualization."""

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import Settings
from app.deps import get_retriever, get_scopedb, get_settings, get_tracking
from app.events import event_bus
from app.rag.retriever import Retriever
from app.ratelimit import STANDARD, limiter
from app.scope_utils import parse_scope_ids, resolve_scopes
from app.tag_utils import resolve_tag_paths
from app.services.graph_service import compute_edge_detail, compute_graph, graph_progress
from app.storage.scopedb import ScopeDB
from app.storage.trackingdb import TrackingDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])

# In-memory cache: key = (frozenset(folders), frozenset(tags), top_k, ...) -> graph data
_graph_cache: dict[tuple, dict] = {}
_cache_lock = threading.Lock()


def _cache_key(
    source_roots: list[str] | None,
    scope_tags: list[str] | None,
    ad_hoc_tags: list[str] | None,
    top_k: int,
    word_clouds: bool = True,
    min_weight: float = 0.0,
) -> tuple:
    roots = frozenset(source_roots) if source_roots else frozenset()
    tags = frozenset(scope_tags) if scope_tags else frozenset()
    adhoc = frozenset(ad_hoc_tags) if ad_hoc_tags else frozenset()
    return (roots, tags, adhoc, top_k, word_clouds, min_weight)


@router.get("/data")
@limiter.limit(STANDARD)
def graph_data(
    request: Request,
    scope_id: str | None = None,
    scope_ids: str | None = None,
    ad_hoc_tags: list[str] | None = Query(None),
    top_k: int = 3,
    word_clouds: bool = True,
    min_weight: float = 0.5,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    scopedb: ScopeDB = Depends(get_scopedb),
    tracking: TrackingDB = Depends(get_tracking),
):
    """Return the full knowledge graph (nodes, edges, clusters, word clouds)."""
    ids = parse_scope_ids(scope_ids) or ([scope_id] if scope_id else None)
    scope_folders, scope_tags = resolve_scopes(ids, scopedb)
    allowed = resolve_tag_paths(scope_tags, ad_hoc_tags)
    key = _cache_key(scope_folders, scope_tags, ad_hoc_tags, top_k, word_clouds, min_weight)

    with _cache_lock:
        if key in _graph_cache:
            return _graph_cache[key]

    result = compute_graph(
        retriever.store, scope_folders, top_k,
        word_clouds=word_clouds, min_weight=min_weight,
        allowed_paths=allowed,
    )

    with _cache_lock:
        _graph_cache[key] = result

    return result


@router.get("/stats")
@limiter.limit(STANDARD)
def graph_stats(
    request: Request,
    scope_id: str | None = None,
    scope_ids: str | None = None,
    retriever: Retriever = Depends(get_retriever),
    scopedb: ScopeDB = Depends(get_scopedb),
    tracking: TrackingDB = Depends(get_tracking),
):
    """Lightweight stats without computing the full graph."""
    ids = parse_scope_ids(scope_ids) or ([scope_id] if scope_id else None)
    scope_folders, scope_tags = resolve_scopes(ids, scopedb)

    if scope_folders:
        raw = retriever.store.get_all_with_embeddings(scope_folders)
        all_meta = raw["metadatas"]
    else:
        all_meta = retriever.store.get_all_metadatas()

    # Apply tag filtering via tracking DB paths
    allowed = resolve_tag_paths(scope_tags, None)
    if allowed is not None:
        all_meta = [
            m for m in all_meta
            if m.get("source_path", "") in allowed
        ]

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
    scope_ids: str | None = None,
    ad_hoc_tags: list[str] | None = Query(None),
    top_k: int = 3,
    word_clouds: bool = True,
    min_weight: float = 0.5,
    scopedb: ScopeDB = Depends(get_scopedb),
):
    """Check if cached graph data is available (no computation)."""
    ids = parse_scope_ids(scope_ids) or ([scope_id] if scope_id else None)
    scope_folders, scope_tags = resolve_scopes(ids, scopedb)
    key = _cache_key(scope_folders, scope_tags, ad_hoc_tags, top_k, word_clouds, min_weight)
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
