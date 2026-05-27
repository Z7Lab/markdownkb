"""Document map endpoints — document similarity visualization."""

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import Settings
from app.deps import get_bucket_service, get_retriever, get_scopedb, get_settings, get_tracking
from app.events import event_bus
from app.rag.retriever import Retriever
from app.ratelimit import STANDARD, limiter
from app.domains.scope_resolution import apply_exclude_patterns, resolve_scopes
from app.services.scope_service import parse_scope_id_fallback as _parse_scope_id_fallback
from app.domains.tag_registry import resolve_tag_paths
from app.services.graph_service import compute_cross_edges_fused, compute_edge_detail, compute_graph, graph_progress
from app.storage.scopedb import ScopeDB
from app.storage.trackingdb import TrackingDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/docmap", tags=["docmap"])

# In-memory cache: key = (frozenset(folders), frozenset(tags), top_k, ...) -> graph data
_graph_cache: dict[tuple, dict] = {}
_cache_lock = threading.Lock()

from app.plugins.docmap.service import cache_key as _cache_key


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
    bucket_ids: str | None = None,
    bucket_min_weight: float = 0.55,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    scopedb: ScopeDB = Depends(get_scopedb),
    tracking: TrackingDB = Depends(get_tracking),
    bucket_service=Depends(get_bucket_service),
):
    """Return the document similarity map (nodes, edges, clusters, word clouds)."""
    ids = _parse_scope_id_fallback(scope_ids, scope_id)
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

    # Merge bucket_id and bucket_ids into a single deduplicated list
    all_bucket_ids: list[str] = []
    seen: set[str] = set()
    for bid in ([bucket_id] if bucket_id else []) + [b for b in (bucket_ids or "").split(",") if b]:
        if bid not in seen:
            all_bucket_ids.append(bid)
            seen.add(bid)

    # Resolve all bucket records up front (needed for cache key — color is baked into nodes)
    bucket_records: list[dict] = []
    if all_bucket_ids and bucket_service:
        for bid in all_bucket_ids:
            rec = bucket_service.db.resolve(bid)
            if rec:
                bucket_records.append(rec)

    # Include bucket IDs, threshold, and colors in cache key — color changes
    # must produce a new cache entry since color is baked into graph nodes.
    cache_buckets = ",".join(sorted(all_bucket_ids))
    cache_bucket_colors = ",".join(r.get("color") or "" for r in bucket_records)
    key = _cache_key(scope_folders, scope_tags, ad_hoc_tags, top_k, word_clouds, min_weight, exclude_patterns)
    key = key + (cache_buckets, bucket_min_weight if all_bucket_ids else 0.0, cache_bucket_colors)

    with _cache_lock:
        if key in _graph_cache:
            return _graph_cache[key]

    excluded = set(tracking.get_excluded_paths())
    result = compute_graph(
        retriever.store, scope_folders, top_k,
        word_clouds=word_clouds, min_weight=min_weight,
        allowed_paths=allowed, excluded_paths=excluded,
    )

    # Merge each bucket's documents into the graph with _bucket tag
    total_cross_edges = 0
    total_bucket_docs = 0
    if bucket_records:
        # Expand scope folders into allowed set once for cross-edge filtering
        cross_allowed = allowed
        if cross_allowed is None and scope_folders:
            all_tracked = tracking.get_all_files()
            cross_allowed = {
                f["path"] for f in all_tracked
                if any(f["path"].startswith(d + "/") or f["path"] == d for d in scope_folders)
            }
        for bucket_record in bucket_records:
            bucket_store = bucket_service.get_store(bucket_record["id"])
            bucket_graph = compute_graph(
                bucket_store, None, top_k,
                word_clouds=word_clouds, min_weight=min_weight,
            )

            bucket_color = bucket_record.get("color") or "#ff3333"
            for node in bucket_graph["nodes"]:
                node["_bucket"] = True
                node["bucket_color"] = bucket_color
            result["nodes"].extend(bucket_graph["nodes"])
            result["edges"].extend(bucket_graph["edges"])

            # Compute cross-collection edges (bucket ↔ main) via Reciprocal
            # Rank Fusion of four signals: mean-top-K cosine (baseline), max
            # chunk-pair cosine, TF-IDF cosine, and relative neighbour rank.
            # See docs/experiments/docmap-edge-weight-strategies.md for the
            # empirical evaluation that motivated this approach. Edges are
            # normalized to [0, 1] per bucket doc, so bucket_min_weight is
            # effectively "show top X% of fused ranks" — every bucket doc
            # always has at least one edge at weight 1.0.
            cross_edges = compute_cross_edges_fused(
                retriever.store, bucket_store,
                top_k=top_k, min_fused_weight=bucket_min_weight,
                allowed_paths_a=cross_allowed, excluded_paths_a=excluded,
            )
            result["edges"].extend(cross_edges)
            total_cross_edges += len(cross_edges)
            total_bucket_docs += bucket_graph["stats"]["doc_count"]
            logger.info("docmap: %d cross-collection edges for bucket %s", len(cross_edges), bucket_record["id"])

            for term, weight in bucket_graph.get("global_word_cloud", {}).items():
                result["global_word_cloud"][term] = max(
                    result["global_word_cloud"].get(term, 0), weight
                )
            result["stats"]["doc_count"] += bucket_graph["stats"]["doc_count"]
            result["stats"]["chunk_count"] += bucket_graph["stats"]["chunk_count"]
            result["stats"]["edge_count"] += len(cross_edges) + bucket_graph["stats"]["edge_count"]

        result["stats"]["bucket_doc_count"] = total_bucket_docs

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
    ids = _parse_scope_id_fallback(scope_ids, scope_id)
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
    ids = _parse_scope_id_fallback(scope_ids, scope_id)
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
    bucket_id: str | None = None,
    retriever: Retriever = Depends(get_retriever),
    bucket_service=Depends(get_bucket_service),
):
    """Return chunk-level similarity detail for a single document pair.

    When ``bucket_id`` is provided, the bucket's vector store is used as a
    second source of chunk data — necessary for cross-collection edges
    (bucket doc ↔ scope doc), which otherwise return empty because the
    bucket doc's chunks don't exist in the main store.
    """
    if not source or not target:
        raise HTTPException(status_code=400, detail="source and target are required")
    bucket_store = _bucket_store_for(bucket_service, bucket_id) if bucket_id else None
    return compute_edge_detail(retriever.store, source, target, top_k, target_store=bucket_store)


# In-memory cache for edge explanations. Keyed by (source_path, target_path,
# source_hash, target_hash). Invalidated on index events (see below) so
# we don't serve stale explanations for docs that have been reindexed.
_explain_cache: dict[tuple, dict] = {}
_explain_cache_lock = threading.Lock()

_EXPLAIN_MAX_CHARS = 3000  # per-doc content budget to keep prompt cost bounded
_EXPLAIN_SYSTEM_PROMPT = (
    "You are analyzing two documents flagged as related in a knowledge map. "
    "Explain in ONE sentence what conceptual overlap connects them. Be concrete, "
    "not generic — name the specific shared idea, pattern, entity, or problem. "
    "If the connection looks weak or spurious, say so briefly instead of forcing a link."
)


def _load_doc_for_explain(
    path: str,
    retriever: Retriever,
    bucket_service,
    bucket_id: str | None,
) -> tuple[str, str] | None:
    """Return (text, content_hash) for the doc at ``path`` or None if missing.
    Tries the main store first, then the selected bucket store. Concatenates
    chunk documents and truncates to ``_EXPLAIN_MAX_CHARS``.
    """
    for store in (retriever.store, _bucket_store_for(bucket_service, bucket_id)):
        if store is None:
            continue
        data = store.get_chunks_for_doc(path)
        docs = data.get("documents") or []
        if not docs:
            continue
        text = "\n\n".join(d for d in docs if d)
        if not text:
            continue
        if len(text) > _EXPLAIN_MAX_CHARS:
            text = text[:_EXPLAIN_MAX_CHARS] + "\n\n[truncated]"
        import hashlib
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return text, h
    return None


def _bucket_store_for(bucket_service, bucket_id: str | None):
    if not bucket_service or not bucket_id:
        return None
    record = bucket_service.db.resolve(bucket_id)
    if not record:
        return None
    return bucket_service.get_store(record["id"])


@router.get("/edge-explain")
@limiter.limit(STANDARD)
def edge_explain(
    request: Request,
    source: str = "",
    target: str = "",
    bucket_id: str | None = None,
    refresh: bool = False,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    bucket_service=Depends(get_bucket_service),
):
    """Generate a one-sentence explanation of why two docs are connected.

    Follows the same LLM-plumbing pattern as ``/search/summarize`` but
    returns a single non-streaming string. Cached in-memory by
    (source, target, content-hashes). ``refresh=true`` bypasses cache.
    """
    if not source or not target:
        raise HTTPException(status_code=400, detail="source and target are required")

    src = _load_doc_for_explain(source, retriever, bucket_service, bucket_id)
    tgt = _load_doc_for_explain(target, retriever, bucket_service, bucket_id)
    if src is None:
        raise HTTPException(status_code=404, detail=f"Source doc not found or empty: {source}")
    if tgt is None:
        raise HTTPException(status_code=404, detail=f"Target doc not found or empty: {target}")

    src_text, src_hash = src
    tgt_text, tgt_hash = tgt
    cache_key = (source, target, src_hash, tgt_hash)

    if not refresh:
        with _explain_cache_lock:
            if cache_key in _explain_cache:
                return {**_explain_cache[cache_key], "cached": True}

    src_name = source.rsplit("/", 1)[-1]
    tgt_name = target.rsplit("/", 1)[-1]
    user_prompt = (
        f"Document A ({src_name}):\n\n{src_text}\n\n"
        f"---\n\n"
        f"Document B ({tgt_name}):\n\n{tgt_text}\n\n"
        f"---\n\n"
        f"In one sentence, what is the conceptual overlap that makes these documents related?"
    )
    messages = [
        {"role": "system", "content": _EXPLAIN_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        from app.rag.llm import get_completion, strip_thinking
        raw = get_completion(messages, settings)
        if not isinstance(raw, str):
            raise RuntimeError("Expected string completion")
        explanation = strip_thinking(raw).strip()
    except RuntimeError as e:
        logger.error("edge-explain LLM error: %s", e)
        raise HTTPException(status_code=503, detail="LLM request failed — check server logs")

    payload = {"explanation": explanation, "source": source, "target": target}
    with _explain_cache_lock:
        _explain_cache[cache_key] = payload
    return {**payload, "cached": False}


@router.get("/progress")
@limiter.limit(STANDARD)
def get_graph_progress(request: Request):
    """Return current graph computation progress."""
    return {
        "fraction": graph_progress["fraction"],
        "phase": graph_progress["phase"],
    }


# Cache invalidation via IndexEventBus
def _invalidation_worker(subscription):
    while True:
        event = subscription.get()
        if event is None:
            break
        if event.type in ("indexed", "deleted", "index_toggled"):
            with _cache_lock:
                _graph_cache.clear()
            with _explain_cache_lock:
                _explain_cache.clear()
            logger.debug("Docmap caches cleared due to %s event", event.type)


_invalidation_thread: threading.Thread | None = None
_invalidation_subscription = None


def start_invalidation_thread() -> None:
    """Start the cache-invalidation worker.

    Called from the docmap plugin's ``on_startup`` hook so the thread is
    only spawned when the plugin is enabled and app state is ready. Must
    not be called from module import — tests that import the router would
    otherwise leak a background thread.
    """
    global _invalidation_thread, _invalidation_subscription
    if _invalidation_thread is not None:
        return
    _invalidation_subscription = event_bus.subscribe()
    _invalidation_thread = threading.Thread(
        target=_invalidation_worker,
        args=(_invalidation_subscription,),
        daemon=True,
        name="graph-cache-invalidation",
    )
    _invalidation_thread.start()


def stop_invalidation_thread() -> None:
    """Signal the cache-invalidation worker to exit and join it briefly."""
    global _invalidation_thread, _invalidation_subscription
    if _invalidation_subscription is not None:
        _invalidation_subscription.put(None)
    if _invalidation_thread is not None:
        _invalidation_thread.join(timeout=2.0)
    _invalidation_thread = None
    _invalidation_subscription = None


