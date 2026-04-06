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


# -- Knowledge Graph endpoints --
#
# The KG database is owned by the graph plugin — created in on_startup,
# stored on app.state.kgdb, closed in on_shutdown.  No core code touches it.


def _get_kgdb(request: Request):
    """Get KnowledgeGraphDB from app.state (plugin-owned)."""
    kgdb = getattr(request.app.state, "kgdb", None)
    if kgdb is None:
        raise HTTPException(503, "Knowledge graph not initialized")
    return kgdb


# Background extraction state — module-level, one extraction at a time.
_extraction_status: dict = {
    "running": False,
    "cancel": threading.Event(),
    "progress": 0.0,
    "message": "",
    "result": "",
    "files_done": 0,
    "files_total": 0,
}
_extraction_lock = threading.Lock()


def _bg_extract(settings, kgdb, tracking):
    """Run KG extraction over all indexed files in a background thread."""
    from app.ingestion.parser import parse_and_chunk
    from app.services.kg_extraction import extract_from_chunks

    try:
        all_files = tracking.get_all_files()
        indexed = [f for f in all_files if f["status"] == "complete"]
        total = len(indexed)

        with _extraction_lock:
            _extraction_status["files_total"] = total
            _extraction_status["files_done"] = 0

        for i, f in enumerate(indexed):
            if _extraction_status["cancel"].is_set():
                with _extraction_lock:
                    _extraction_status["message"] = "Cancelled"
                    _extraction_status["result"] = f"Cancelled after {i}/{total} files"
                break

            path = f["path"]
            source_root = f["source_root"]
            frac = i / max(total, 1)

            with _extraction_lock:
                _extraction_status["progress"] = frac
                _extraction_status["message"] = f"Extracting from {path.split('/')[-1]}..."
                _extraction_status["files_done"] = i

            try:
                chunks = parse_and_chunk(
                    path, source_root,
                    settings.chunk_size, settings.chunk_overlap,
                )
                if chunks:
                    kgdb.delete_by_source(path)
                    extract_from_chunks(chunks, path, kgdb, settings)
            except Exception:
                logger.warning("KG extraction failed for %s", path, exc_info=True)

        with _extraction_lock:
            stats = kgdb.get_stats()
            _extraction_status["progress"] = 1.0
            _extraction_status["files_done"] = total
            if not _extraction_status["cancel"].is_set():
                _extraction_status["message"] = "Done"
                _extraction_status["result"] = (
                    f"Extracted {stats['unique_entities']} entities, "
                    f"{stats['relationships']} relationships from {stats['source_files']} files"
                )
    except Exception as e:
        logger.error("KG extraction failed: %s", e, exc_info=True)
        with _extraction_lock:
            _extraction_status["result"] = f"Error: {e}"
    finally:
        with _extraction_lock:
            _extraction_status["running"] = False


@router.post("/kg/extract")
@limiter.limit(STANDARD)
def kg_extract(request: Request, settings: Settings = Depends(get_settings)):
    """Start background KG extraction over all indexed files."""
    kgdb = _get_kgdb(request)
    tracking = request.app.state.tracking

    with _extraction_lock:
        if _extraction_status["running"]:
            raise HTTPException(409, "Extraction already in progress")
        _extraction_status["running"] = True
        _extraction_status["cancel"].clear()
        _extraction_status["progress"] = 0.0
        _extraction_status["message"] = "Starting extraction..."
        _extraction_status["result"] = ""
        _extraction_status["files_done"] = 0
        _extraction_status["files_total"] = 0

    threading.Thread(
        target=_bg_extract,
        args=(settings, kgdb, tracking),
        daemon=True,
    ).start()
    return {"status": "started"}


@router.post("/kg/extract/cancel")
@limiter.limit(STANDARD)
def kg_extract_cancel(request: Request):
    """Cancel a running KG extraction."""
    _extraction_status["cancel"].set()
    return {"status": "cancelling"}


@router.get("/kg/extract/status")
@limiter.limit(STANDARD)
def kg_extract_status(request: Request):
    """Return current KG extraction progress."""
    with _extraction_lock:
        return {
            "running": _extraction_status["running"],
            "progress": _extraction_status["progress"],
            "message": _extraction_status["message"],
            "result": _extraction_status["result"],
            "files_done": _extraction_status["files_done"],
            "files_total": _extraction_status["files_total"],
        }


@router.get("/kg/data")
@limiter.limit(STANDARD)
def kg_data(
    request: Request,
    entity_types: str | None = Query(None, description="Comma-separated entity types"),
    rel_types: str | None = Query(None, description="Comma-separated relationship types"),
):
    """Return knowledge graph entities and relationships for visualization."""
    kgdb = _get_kgdb(request)

    et = [t.strip() for t in entity_types.split(",")] if entity_types else None
    rt = [t.strip() for t in rel_types.split(",")] if rel_types else None

    entities = kgdb.get_all_entities(entity_types=et)
    relationships = kgdb.get_all_relationships(rel_types=rt)

    return {
        "entities": entities,
        "relationships": relationships,
        "entity_types": kgdb.get_entity_types(),
        "relationship_types": kgdb.get_relationship_types(),
        "stats": kgdb.get_stats(),
    }


@router.get("/kg/entity")
@limiter.limit(STANDARD)
def kg_entity(
    request: Request,
    name: str = Query(..., description="Entity name"),
):
    """Return a single entity with all its relationships."""
    kgdb = _get_kgdb(request)
    entity = kgdb.get_entity(name)
    if entity is None:
        raise HTTPException(404, f"Entity not found: {name}")
    return entity


@router.get("/kg/path")
@limiter.limit(STANDARD)
def kg_path(
    request: Request,
    source: str = Query(..., description="Source entity name"),
    target: str = Query(..., description="Target entity name"),
    max_hops: int = Query(6, ge=1, le=20),
):
    """Find the shortest path between two entities."""
    kgdb = _get_kgdb(request)
    path = kgdb.find_path(source, target, max_hops=max_hops)
    if path is None:
        return {"path": None, "message": f"No path found between '{source}' and '{target}'"}
    return {"path": path}


@router.get("/kg/stats")
@limiter.limit(STANDARD)
def kg_stats(request: Request):
    """Return knowledge graph statistics."""
    kgdb = getattr(request.app.state, "kgdb", None)
    if kgdb is None:
        return {"entity_mentions": 0, "unique_entities": 0, "relationships": 0, "source_files": 0, "cached_chunks": 0}
    return kgdb.get_stats()


@router.post("/kg/clear")
@limiter.limit(STANDARD)
def kg_clear(request: Request):
    """Clear all knowledge graph data. Run extraction to rebuild."""
    kgdb = _get_kgdb(request)
    kgdb.clear()
    return {"status": "cleared"}
