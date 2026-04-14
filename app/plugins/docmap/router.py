"""Document map endpoints — document similarity visualization."""

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import Settings
from app.deps import get_retriever, get_scopedb, get_settings, get_tracking
from app.events import event_bus
from app.rag.retriever import Retriever
from app.ratelimit import STANDARD, limiter
from app.scope_utils import apply_exclude_patterns, parse_scope_ids, resolve_scopes
from app.tag_utils import resolve_tag_paths
from app.services.graph_service import compute_cross_edges_fused, compute_edge_detail, compute_graph, graph_progress
from app.storage.scopedb import ScopeDB
from app.storage.trackingdb import TrackingDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/docmap", tags=["docmap"])

# In-memory cache: key = (frozenset(folders), frozenset(tags), top_k, ...) -> graph data
_graph_cache: dict[tuple, dict] = {}
_cache_lock = threading.Lock()

_debug_log_lock = threading.Lock()


def _debug_log_path(settings: Settings) -> Path:
    return Path(settings.data_directory) / "docmap-debug.log"


def _debug_log(settings: Settings, line: str) -> None:
    """Append a line to the docmap debug log. Best effort — swallow errors."""
    try:
        path = _debug_log_path(settings)
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with _debug_log_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {line}\n")
    except Exception:
        pass


def _debug_log_build(
    settings: Settings,
    *,
    scope_ids_raw: str | None,
    scope_name: str | None,
    scope_folders: list[str] | None,
    bucket_id: str | None,
    bucket_name: str | None,
    min_weight: float,
    client_threshold: float | None,
    bucket_min_weight: float,
    word_clouds: bool,
    cache_status: str,
    main_doc_count: int,
    main_edge_count: int,
    bucket_doc_count: int,
    bucket_intra_edge_count: int,
    cross_edges: list[dict],
) -> None:
    """Write one multi-line block summarising a build. Keeps lines tight."""
    scope_desc = scope_name or scope_ids_raw or "all"
    bucket_desc = bucket_name or bucket_id or "-"
    threshold_str = f"{client_threshold:.2f}" if client_threshold is not None else "?"
    header = (
        f"{cache_status} scope={scope_desc} bucket={bucket_desc} "
        f"threshold={threshold_str} min_weight={min_weight:.2f} "
        f"bucket_min_weight={bucket_min_weight:.2f} wc={'on' if word_clouds else 'off'}"
    )
    _debug_log(settings, header)
    if cache_status == "HIT":
        return
    _debug_log(
        settings,
        f"  main={main_doc_count}d/{main_edge_count}e  "
        f"bucket={bucket_doc_count}d/{bucket_intra_edge_count}e  "
        f"cross={len(cross_edges)}",
    )
    if cross_edges:
        _debug_log(settings, "  overlap:")
        for e in sorted(cross_edges, key=lambda x: -x["weight"])[:10]:
            src_name = e["source"].rsplit("/", 1)[-1]
            tgt_name = e["target"].rsplit("/", 1)[-1]
            _debug_log(settings, f"    {tgt_name}  <->  {src_name}  w={e['weight']:.4f}")


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
    bucket_min_weight: float = 0.55,
    client_threshold: float | None = None,
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

    # Include bucket_id and bucket_min_weight in cache key — different
    # bucket thresholds produce different edge sets and must not share a
    # cache entry.
    cache_bucket = bucket_id or ""
    key = _cache_key(scope_folders, scope_tags, ad_hoc_tags, top_k, word_clouds, min_weight, exclude_patterns)
    key = key + (cache_bucket, bucket_min_weight if bucket_id else 0.0)

    # Resolve human-readable scope/bucket names for the debug log.
    scope_name = None
    if ids:
        rows = [scopedb.get(s) for s in ids]
        names = [r["name"] for r in rows if r]
        scope_name = ", ".join(names) if names else None
    bucket_name = None
    bucket_record = None
    if bucket_id:
        bucket_service = getattr(request.app.state, "bucket_service", None)
        if bucket_service:
            bucket_record = bucket_service.db.resolve(bucket_id)
            if bucket_record:
                bucket_name = bucket_record.get("name")

    with _cache_lock:
        if key in _graph_cache:
            cached = _graph_cache[key]
            _debug_log_build(
                settings,
                scope_ids_raw=scope_ids,
                scope_name=scope_name,
                scope_folders=scope_folders,
                bucket_id=bucket_id,
                bucket_name=bucket_name,
                min_weight=min_weight,
                client_threshold=client_threshold,
                bucket_min_weight=bucket_min_weight,
                word_clouds=word_clouds,
                cache_status="HIT",
                main_doc_count=0, main_edge_count=0,
                bucket_doc_count=0, bucket_intra_edge_count=0,
                cross_edges=[],
            )
            return cached

    excluded = set(tracking.get_rag_excluded_paths())
    result = compute_graph(
        retriever.store, scope_folders, top_k,
        word_clouds=word_clouds, min_weight=min_weight,
        allowed_paths=allowed, excluded_paths=excluded,
    )

    main_doc_count = result["stats"]["doc_count"]
    main_edge_count = result["stats"]["edge_count"]
    bucket_doc_count = 0
    bucket_intra_edge_count = 0
    cross_edges: list[dict] = []

    # Merge bucket documents into the graph with _bucket tag
    if bucket_id and bucket_record:
        bucket_service = request.app.state.bucket_service
        bucket_store = bucket_service.get_store(bucket_record["id"])
        bucket_graph = compute_graph(
            bucket_store, None, top_k,
            word_clouds=word_clouds, min_weight=min_weight,
        )
        bucket_doc_count = bucket_graph["stats"]["doc_count"]
        bucket_intra_edge_count = bucket_graph["stats"]["edge_count"]

        # Tag bucket nodes and apply the bucket's color
        bucket_color = bucket_record.get("color") or "#ff3333"
        for node in bucket_graph["nodes"]:
            node["_bucket"] = True
            node["bucket_color"] = bucket_color
        # Merge nodes and intra-bucket edges
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
        #
        # compute_cross_edges_fused only post-filters via allowed_paths_a;
        # it has no concept of scope_folders. So if the scope is folder-
        # only (tags/excludes already expanded above leave scope_folders
        # set with allowed=None), we must expand folders into an explicit
        # allowed set here, otherwise cross-edges leak across the scope
        # boundary and the bucket connects to the global-top neighbours
        # instead of scope-top neighbours.
        cross_allowed = allowed
        if cross_allowed is None and scope_folders:
            all_tracked = tracking.get_all_files()
            cross_allowed = {
                f["path"] for f in all_tracked
                if any(f["path"].startswith(d + "/") or f["path"] == d for d in scope_folders)
            }
        cross_edges = compute_cross_edges_fused(
            retriever.store, bucket_store,
            top_k=top_k, min_fused_weight=bucket_min_weight,
            allowed_paths_a=cross_allowed, excluded_paths_a=excluded,
        )
        result["edges"].extend(cross_edges)
        logger.info("docmap: %d cross-collection edges between main and bucket", len(cross_edges))

        # Merge word clouds
        for term, weight in bucket_graph.get("global_word_cloud", {}).items():
            result["global_word_cloud"][term] = max(
                result["global_word_cloud"].get(term, 0), weight
            )
        # Update stats
        result["stats"]["doc_count"] += bucket_doc_count
        result["stats"]["chunk_count"] += bucket_graph["stats"]["chunk_count"]
        result["stats"]["edge_count"] += len(cross_edges) + bucket_intra_edge_count
        result["stats"]["bucket_doc_count"] = bucket_doc_count

    bucket_nodes = sum(1 for n in result["nodes"] if n.get("_bucket"))
    logger.info("docmap/data result: %d nodes (%d bucket), %d edges", len(result["nodes"]), bucket_nodes, len(result["edges"]))

    _debug_log_build(
        settings,
        scope_ids_raw=scope_ids,
        scope_name=scope_name,
        scope_folders=scope_folders,
        bucket_id=bucket_id,
        bucket_name=bucket_name,
        min_weight=min_weight,
        client_threshold=client_threshold,
        bucket_min_weight=bucket_min_weight,
        word_clouds=word_clouds,
        cache_status="BUILD",
        main_doc_count=main_doc_count,
        main_edge_count=main_edge_count,
        bucket_doc_count=bucket_doc_count,
        bucket_intra_edge_count=bucket_intra_edge_count,
        cross_edges=cross_edges,
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
    bucket_id: str | None = None,
    retriever: Retriever = Depends(get_retriever),
):
    """Return chunk-level similarity detail for a single document pair.

    When ``bucket_id`` is provided, the bucket's vector store is used as a
    second source of chunk data — necessary for cross-collection edges
    (bucket doc ↔ scope doc), which otherwise return empty because the
    bucket doc's chunks don't exist in the main store.
    """
    if not source or not target:
        raise HTTPException(status_code=400, detail="source and target are required")
    bucket_service = getattr(request.app.state, "bucket_service", None)
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
):
    """Generate a one-sentence explanation of why two docs are connected.

    Follows the same LLM-plumbing pattern as ``/search/summarize`` but
    returns a single non-streaming string. Cached in-memory by
    (source, target, content-hashes). ``refresh=true`` bypasses cache.
    """
    if not source or not target:
        raise HTTPException(status_code=400, detail="source and target are required")

    bucket_service = getattr(request.app.state, "bucket_service", None)

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
def _invalidation_worker():
    q = event_bus.subscribe()
    while True:
        event = q.get()
        if event is None:
            break
        if event.type in ("indexed", "deleted", "rag_toggled"):
            with _cache_lock:
                _graph_cache.clear()
            with _explain_cache_lock:
                _explain_cache.clear()
            logger.debug("Docmap caches cleared due to %s event", event.type)


_invalidation_thread = threading.Thread(
    target=_invalidation_worker, daemon=True, name="graph-cache-invalidation",
)
_invalidation_thread.start()


