"""Graph endpoints for knowledge graph visualization."""

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import Settings
from app.deps import get_retriever, get_scopedb, get_settings, get_tracking
from app.events import event_bus
from app.rag.retriever import Retriever
from app.ratelimit import STANDARD, limiter
from app.services.graph_service import compute_edge_detail, compute_graph, graph_progress
from app.storage.scopedb import ScopeDB
from app.storage.trackingdb import TrackingDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])

# In-memory cache: key = (frozenset(folders), frozenset(tags), top_k, ...) -> graph data
_graph_cache: dict[tuple, dict] = {}
_cache_lock = threading.Lock()


def _resolve_scopes(
    scope_ids: list[str] | None, scopedb: ScopeDB,
) -> tuple[list[str] | None, list[str] | None]:
    """Resolve one or more scope IDs into merged (folders, tags).

    Returns (folders_or_None, tags_or_None).
    """
    if not scope_ids:
        return None, None

    all_folders: list[str] = []
    all_tags: list[str] = []
    for sid in scope_ids:
        scope = scopedb.get(sid)
        if not scope:
            raise HTTPException(status_code=404, detail=f"Scope not found: {sid}")
        all_folders.extend(scope["folders"])
        all_tags.extend(scope["tags"])

    # Deduplicate while preserving order
    folders = list(dict.fromkeys(all_folders)) or None
    tags = list(dict.fromkeys(all_tags)) or None
    return folders, tags


def _resolve_tag_paths(
    scope_tags: list[str] | None, tracking: TrackingDB,
) -> set[str] | None:
    """Resolve scope tags to a set of allowed file paths via tracking DB."""
    if not scope_tags:
        return None
    tag_set = set(scope_tags)
    paths = set()
    for f in tracking.get_all_files():
        file_tags = {t.strip() for t in f.get("tags", "").split(",") if t.strip()}
        if tag_set.intersection(file_tags):
            paths.add(f["path"])
    return paths


def _parse_scope_ids(scope_ids: str | None) -> list[str] | None:
    """Parse comma-separated scope_ids query param."""
    if not scope_ids:
        return None
    ids = [s.strip() for s in scope_ids.split(",") if s.strip()]
    return ids or None


def _cache_key(
    source_roots: list[str] | None,
    scope_tags: list[str] | None,
    top_k: int,
    word_clouds: bool = True,
    min_weight: float = 0.0,
) -> tuple:
    roots = frozenset(source_roots) if source_roots else frozenset()
    tags = frozenset(scope_tags) if scope_tags else frozenset()
    return (roots, tags, top_k, word_clouds, min_weight)


@router.get("/data")
@limiter.limit(STANDARD)
def graph_data(
    request: Request,
    scope_id: str | None = None,
    scope_ids: str | None = None,
    top_k: int = 3,
    word_clouds: bool = True,
    min_weight: float = 0.5,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    scopedb: ScopeDB = Depends(get_scopedb),
    tracking: TrackingDB = Depends(get_tracking),
):
    """Return the full knowledge graph (nodes, edges, clusters, word clouds)."""
    ids = _parse_scope_ids(scope_ids) or ([scope_id] if scope_id else None)
    scope_folders, scope_tags = _resolve_scopes(ids, scopedb)
    allowed = _resolve_tag_paths(scope_tags, tracking)
    key = _cache_key(scope_folders, scope_tags, top_k, word_clouds, min_weight)

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
    ids = _parse_scope_ids(scope_ids) or ([scope_id] if scope_id else None)
    scope_folders, scope_tags = _resolve_scopes(ids, scopedb)

    if scope_folders:
        raw = retriever.store.get_all_with_embeddings(scope_folders)
        all_meta = raw["metadatas"]
    else:
        all_meta = retriever.store.get_all_metadatas()

    # Apply tag filtering via tracking DB paths
    allowed = _resolve_tag_paths(scope_tags, tracking)
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
    top_k: int = 3,
    word_clouds: bool = True,
    min_weight: float = 0.5,
    scopedb: ScopeDB = Depends(get_scopedb),
):
    """Check if cached graph data is available (no computation)."""
    ids = _parse_scope_ids(scope_ids) or ([scope_id] if scope_id else None)
    scope_folders, scope_tags = _resolve_scopes(ids, scopedb)
    key = _cache_key(scope_folders, scope_tags, top_k, word_clouds, min_weight)
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
