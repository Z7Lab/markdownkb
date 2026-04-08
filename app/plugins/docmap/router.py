"""Document map endpoints — document similarity visualization."""

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import Settings
from app.deps import get_retriever, get_scopedb, get_settings, get_tracking
from app.events import event_bus
from app.rag.retriever import Retriever
from app.ratelimit import STANDARD, limiter
from app.scope_utils import apply_exclude_patterns, parse_scope_ids, resolve_scopes
from app.tag_utils import resolve_tag_paths
from app.services.graph_service import compute_cross_edges, compute_edge_detail, compute_graph, graph_progress
from app.storage.scopedb import ScopeDB
from app.storage.trackingdb import TrackingDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/docmap", tags=["docmap"])

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
    exclude_patterns: list[str] | None = None,
) -> tuple:
    roots = frozenset(source_roots) if source_roots else frozenset()
    tags = frozenset(scope_tags) if scope_tags else frozenset()
    adhoc = frozenset(ad_hoc_tags) if ad_hoc_tags else frozenset()
    excludes = frozenset(exclude_patterns) if exclude_patterns else frozenset()
    return (roots, tags, adhoc, top_k, word_clouds, min_weight, excludes)


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
    bucket_id: str | None = None,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    scopedb: ScopeDB = Depends(get_scopedb),
    tracking: TrackingDB = Depends(get_tracking),
):
    """Return the document similarity map (nodes, edges, clusters, word clouds)."""
    ids = parse_scope_ids(scope_ids) or ([scope_id] if scope_id else None)
    logger.info("docmap/data request: scope_ids=%s, bucket_id=%s, min_weight=%s, word_clouds=%s", scope_ids, bucket_id, min_weight, word_clouds)
    scope_folders, scope_tags, exclude_patterns = resolve_scopes(ids, scopedb)
    tag_paths = resolve_tag_paths(scope_tags, ad_hoc_tags)

    # When scopes combine folders AND tags, use OR logic: show docs from
    # the selected folders PLUS docs matching the selected tags.  Without
    # this, tag-based scopes filter out all folder-matched docs.
    # When only tags are active (no folders), pass tag_paths as the filter.
    # When only folders are active (no tags), pass None (no path filter).
    if scope_folders and tag_paths is not None:
        # Union: get all files from the folder scopes, add tag-matched files
        all_tracked = tracking.get_all_files()
        folder_paths = {
            f["path"] for f in all_tracked
            if any(f["path"].startswith(d + "/") or f["path"] == d for d in scope_folders)
        }
        allowed = folder_paths | tag_paths
        # Pass no folder filter to ChromaDB — we filter by allowed_paths instead
        scope_folders = None
    elif tag_paths is not None:
        allowed = tag_paths
    else:
        allowed = None

    # Apply scope exclude patterns — if we have excludes but no allowed set yet,
    # build the path set from folders so we can filter it
    if exclude_patterns and allowed is None and scope_folders:
        all_tracked = tracking.get_all_files()
        allowed = {
            f["path"] for f in all_tracked
            if any(f["path"].startswith(d + "/") or f["path"] == d for d in scope_folders)
        }
        scope_folders = None  # filtering via allowed_paths now
    allowed = apply_exclude_patterns(allowed, exclude_patterns)

    # Include bucket_id in cache key
    cache_bucket = bucket_id or ""
    key = _cache_key(scope_folders, scope_tags, ad_hoc_tags, top_k, word_clouds, min_weight, exclude_patterns)
    key = key + (cache_bucket,)

    with _cache_lock:
        if key in _graph_cache:
            return _graph_cache[key]

    excluded = set(tracking.get_rag_excluded_paths())
    result = compute_graph(
        retriever.store, scope_folders, top_k,
        word_clouds=word_clouds, min_weight=min_weight,
        allowed_paths=allowed, excluded_paths=excluded,
    )

    # Merge bucket documents into the graph with _bucket tag
    if bucket_id:
        bucket_service = getattr(request.app.state, "bucket_service", None)
        if bucket_service:
            record = bucket_service.db.resolve(bucket_id)
            if record:
                bucket_store = bucket_service.get_store(record["id"])
                bucket_graph = compute_graph(
                    bucket_store, None, top_k,
                    word_clouds=word_clouds, min_weight=min_weight,
                )
                # Tag bucket nodes
                for node in bucket_graph["nodes"]:
                    node["_bucket"] = True
                # Merge nodes and intra-bucket edges
                result["nodes"].extend(bucket_graph["nodes"])
                result["edges"].extend(bucket_graph["edges"])

                # Compute cross-collection edges (bucket ↔ main)
                # Use a higher threshold for cross-edges — only show strong
                # connections, otherwise bucket nodes attract everything
                cross_min_weight = max(min_weight, 0.75)
                cross_edges = compute_cross_edges(
                    retriever.store, bucket_store,
                    top_k=top_k, min_weight=cross_min_weight,
                    allowed_paths_a=allowed, excluded_paths_a=excluded,
                )
                result["edges"].extend(cross_edges)
                logger.info("docmap: %d cross-collection edges between main and bucket", len(cross_edges))

                # Merge word clouds
                for term, weight in bucket_graph.get("global_word_cloud", {}).items():
                    result["global_word_cloud"][term] = max(
                        result["global_word_cloud"].get(term, 0), weight
                    )
                # Update stats
                result["stats"]["doc_count"] += bucket_graph["stats"]["doc_count"]
                result["stats"]["chunk_count"] += bucket_graph["stats"]["chunk_count"]
                result["stats"]["edge_count"] += len(cross_edges) + bucket_graph["stats"]["edge_count"]
                result["stats"]["bucket_doc_count"] = bucket_graph["stats"]["doc_count"]

    bucket_nodes = sum(1 for n in result["nodes"] if n.get("_bucket"))
    logger.info("docmap/data result: %d nodes (%d bucket), %d edges", len(result["nodes"]), bucket_nodes, len(result["edges"]))

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
    scope_folders, scope_tags, exclude_patterns = resolve_scopes(ids, scopedb)
    tag_paths = resolve_tag_paths(scope_tags, None)

    all_meta = retriever.store.get_all_metadatas()

    # Build allowed set using same OR logic as /data endpoint
    if scope_folders and tag_paths is not None:
        all_tracked = tracking.get_all_files()
        folder_paths = {
            f["path"] for f in all_tracked
            if any(f["path"].startswith(d + "/") or f["path"] == d for d in scope_folders)
        }
        allowed = folder_paths | tag_paths
    elif scope_folders:
        all_tracked = tracking.get_all_files()
        allowed = {
            f["path"] for f in all_tracked
            if any(f["path"].startswith(d + "/") or f["path"] == d for d in scope_folders)
        }
    elif tag_paths is not None:
        allowed = tag_paths
    else:
        allowed = None

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
    scope_folders, scope_tags, exclude_patterns = resolve_scopes(ids, scopedb)
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
        if event.type in ("indexed", "deleted", "rag_toggled"):
            with _cache_lock:
                _graph_cache.clear()
            logger.debug("Docmap cache cleared due to %s event", event.type)


_invalidation_thread = threading.Thread(
    target=_invalidation_worker, daemon=True, name="graph-cache-invalidation",
)
_invalidation_thread.start()


