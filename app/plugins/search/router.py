"""Search endpoints with history and AI summary."""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_retriever, get_scopedb, get_searchdb, get_settings, get_tracking
from app.rag.llm import get_streaming_completion
from app.rag.prompts import format_context, get_search_summary_user
from app.rag.retriever import Retriever
from app.ratelimit import HEAVY, LLM, STANDARD, limiter
from app.schemas import RenameSearchRequest, SearchRequest, SummarizeRequest
from app.scope_utils import parse_scope_ids, resolve_scopes
from app.tag_utils import resolve_tag_paths
from app.services.chat_service import strip_thinking, extract_unique_sources
from app.services.query_service import build_enhanced_search_query, enhance_query
from app.storage.scopedb import ScopeDB
from app.storage.trackingdb import TrackingDB
from app.storage.searchdb import SearchDB
from app.utils import sse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])

# Plugin config defaults — overridable via plugins.search in settings.yaml
_DEFAULTS = {
    "chunk_multiplier": 10,
    "exact_phrase_multiplier": 20,
    "exact_phrase_matching": True,
}


def _cfg(settings: Settings) -> dict:
    """Return search plugin config with defaults applied."""
    return {**_DEFAULTS, **settings.get_plugin_config("search")}


def _group_results_by_file(results: list) -> list[dict]:
    """Group search results by source file, merging chunks into file-level results.

    For each file:
    - Use max score across all chunks as file relevance
    - Collect all chunk texts as snippets
    - Track chunk count and score statistics

    Returns list of file-level results sorted by max score (descending).
    """
    from collections import defaultdict

    # Group chunks by source_path
    file_groups = defaultdict(list)
    for r in results:
        path = r.metadata.get("source_path", "")
        if path:
            file_groups[path].append(r)

    # Build file-level results
    grouped = []
    for path, chunks in file_groups.items():
        # Calculate file-level score (max across chunks)
        scores = [c.score for c in chunks]
        max_score = max(scores)
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)

        # Collect snippets with their metadata
        snippets = [
            {
                "text": c.document,
                "score": c.score,
                "heading": c.metadata.get("heading", ""),
            }
            for c in chunks
        ]

        # Sort snippets by score (best first)
        snippets.sort(key=lambda s: s["score"], reverse=True)

        # Use primary chunk's metadata (highest scoring chunk)
        primary_chunk = max(chunks, key=lambda c: c.score)

        grouped.append({
            "document": primary_chunk.document,  # Best matching chunk
            "snippets": snippets,
            "metadata": primary_chunk.metadata,
            "score": max_score,
            "chunk_count": len(chunks),
            "score_min": min_score,
            "score_max": max_score,
            "score_avg": avg_score,
        })

    # Sort by max score (descending)
    grouped.sort(key=lambda x: x["score"], reverse=True)

    return grouped


@router.post("/search")
@limiter.limit(HEAVY)
def search(
    request: Request,
    req: SearchRequest,
    retriever: Retriever = Depends(get_retriever),
    searchdb: SearchDB = Depends(get_searchdb),
    scopedb: ScopeDB = Depends(get_scopedb),
    settings: Settings = Depends(get_settings),
    tracking: TrackingDB = Depends(get_tracking),
):
    """Search the vector database with optional intelligent query enhancement."""
    # Bucket-scoped search: delegate to BucketService if bucket_id is set
    if req.bucket_id:
        bucket_service = getattr(request.app.state, "bucket_service", None)
        if bucket_service is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="Buckets plugin not initialized")
        top_k = req.top_k if req.top_k is not None else settings.top_k
        bucket_result = bucket_service.search(req.bucket_id, req.query, top_k, settings)
        # Wrap in SearchResponse format for the frontend
        results = [
            {
                "document": r["content"],
                "metadata": {"source_path": r["source"]},
                "score": r["score"],
                "snippets": [{"text": r["content"], "score": r["score"], "heading": ""}],
                "chunk_count": 1,
                "score_min": r["score"],
                "score_max": r["score"],
                "score_avg": r["score"],
            }
            for r in bucket_result["results"]
        ]
        result_paths = [r["metadata"]["source_path"] for r in results if r.get("metadata", {}).get("source_path")]
        result_details = [{"path": r["metadata"]["source_path"], "score": r["score"]} for r in results]
        search_id = searchdb.save_search(
            req.query, req.folder, req.tag,
            result_paths=result_paths,
            result_count=len(results),
            result_details=result_details,
            result_data=results,
            parent_id=req.parent_id,
        )
        return {
            "results": results,
            "search_id": search_id,
            "query": req.query,
            "is_historical": False,
            "bucket_id": req.bucket_id,
        }

    cfg = _cfg(settings)
    ids = parse_scope_ids(req.scope_ids) or ([req.scope_id] if req.scope_id else None)
    scope_folders, scope_tags = resolve_scopes(ids, scopedb)
    allowed = resolve_tag_paths(scope_tags, req.ad_hoc_tags)
    # Extract "quoted phrases" for exact post-filtering when enabled
    exact_phrases: list[str] = []
    if cfg["exact_phrase_matching"]:
        exact_phrases = [m.lower() for m in re.findall(r'"([^"]+)"', req.query)]
    search_query = req.query.replace('"', '') if exact_phrases else req.query
    llm_offline = False
    top_k = req.top_k if req.top_k is not None else settings.top_k

    # Optionally enhance query with LLM
    if settings.intelligent_search_enabled:
        enhanced = enhance_query(search_query, settings)
        if enhanced.error:
            logger.warning("Intelligent search failed, using original query: %s", enhanced.error)
            llm_offline = True
        else:
            # Build enhanced query from LLM extraction
            search_query = build_enhanced_search_query(enhanced)
            logger.info("Enhanced query: %s -> %s", req.query, search_query)

    # Fetch more chunks to ensure file diversity
    multiplier = cfg["exact_phrase_multiplier"] if exact_phrases else cfg["chunk_multiplier"]
    chunk_fetch_limit = top_k * multiplier
    chunk_results = retriever.search(
        search_query,
        top_k=chunk_fetch_limit,
        folder_filter=req.folder,
        folders_filter=scope_folders or None,
        tag_filter=req.tag,
        allowed_paths=allowed,
    )

    # Post-filter: if quoted phrases were used, only keep chunks containing them
    if exact_phrases:
        filtered = [r for r in chunk_results if all(p in r.document.lower() for p in exact_phrases)]
        logger.info("Exact phrase filter: %d -> %d chunks", len(chunk_results), len(filtered))
        chunk_results = filtered

    # Group chunks by file for cleaner results
    grouped_results = _group_results_by_file(chunk_results)

    # Limit to top_k files (not chunks)
    grouped_results = grouped_results[:top_k]

    # Extract result metadata for history preservation (file-level)
    result_paths = [r["metadata"].get("source_path", "") for r in grouped_results]
    result_count = len(grouped_results)
    result_details = [
        {"path": r["metadata"].get("source_path", ""), "score": r["score"]}
        for r in grouped_results
    ]

    # Serialize grouped results for original view preservation
    # Convert metadata to plain dict for JSON serialization
    result_data = [
        {
            "document": r["document"],
            "snippets": r.get("snippets", []),
            "metadata": dict(r["metadata"]),
            "score": r["score"],
            "chunk_count": r.get("chunk_count"),
            "score_min": r.get("score_min"),
            "score_max": r.get("score_max"),
            "score_avg": r.get("score_avg"),
        }
        for r in grouped_results
    ]

    # Resolve parent_id to the root of the chain (for re-queries)
    parent_id = None
    if req.parent_id:
        parent_search = searchdb.get_search(req.parent_id)
        if parent_search:
            # If the parent itself has a parent, use that (the root)
            parent_id = parent_search.get("parent_id") or req.parent_id

    # Auto-save search to history with full result data
    search_id = searchdb.save_search(
        req.query,
        req.folder,
        req.tag,
        result_paths=result_paths,
        result_count=result_count,
        result_details=result_details,
        result_data=result_data,
        parent_id=parent_id,
    )

    return {
        "results": grouped_results,
        "search_id": search_id,
        "llm_offline": llm_offline,
        "is_historical": False,
    }


@router.get("/searches")
@limiter.limit(STANDARD)
def list_searches(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    searchdb: SearchDB = Depends(get_searchdb),
):
    """List search history with pagination."""
    items = searchdb.list_searches(offset=offset, limit=limit)
    total = searchdb.search_count()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/searches/{search_id}/load")
@limiter.limit(STANDARD)
def load_historical_search(
    request: Request,
    search_id: str,
    searchdb: SearchDB = Depends(get_searchdb),
):
    """
    Load a historical search with its preserved results (fast).

    Returns stored result_data, summary, and version count without
    re-running the search. Use /compare for change detection.
    """
    search_record = searchdb.get_search(search_id)
    if not search_record:
        raise HTTPException(status_code=404, detail="Search not found")

    searchdb.mark_viewed(search_id)

    results_to_return = search_record.get("result_data", [])
    versions = searchdb.get_search_versions(search_id)

    return {
        "results": results_to_return,
        "search_id": search_id,
        "query": search_record["query"],
        "folder": search_record.get("folder"),
        "tag": search_record.get("tag"),
        "summary": search_record.get("summary"),
        "created_at": search_record["created_at"],
        "is_historical": True,
        "version_count": len(versions),
    }


@router.get("/searches/{search_id}/compare")
@limiter.limit(HEAVY)
def compare_historical_search(
    request: Request,
    search_id: str,
    searchdb: SearchDB = Depends(get_searchdb),
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
):
    """
    Compare a historical search against current KB state (slow).

    Re-runs the search to detect what has changed since the original query.
    Called lazily after the fast load completes.
    """
    search_record = searchdb.get_search(search_id)
    if not search_record:
        raise HTTPException(status_code=404, detail="Search not found")

    cfg = _cfg(settings)
    # Re-run search with current KB state for comparison
    raw_query = search_record["query"]
    cmp_phrases: list[str] = []
    if cfg["exact_phrase_matching"]:
        cmp_phrases = [m.lower() for m in re.findall(r'"([^"]+)"', raw_query)]
    search_query = raw_query.replace('"', '') if cmp_phrases else raw_query
    if settings.intelligent_search_enabled:
        enhanced = enhance_query(search_query, settings)
        if not enhanced.error:
            search_query = build_enhanced_search_query(enhanced)

    multiplier = cfg["exact_phrase_multiplier"] if cmp_phrases else cfg["chunk_multiplier"]
    chunk_fetch_limit = settings.top_k * multiplier
    chunk_results = retriever.search(
        search_query,
        top_k=chunk_fetch_limit,
        folder_filter=search_record.get("folder"),
        tag_filter=search_record.get("tag"),
    )
    if cmp_phrases:
        chunk_results = [r for r in chunk_results if all(p in r.document.lower() for p in cmp_phrases)]
    current_grouped_results = _group_results_by_file(chunk_results)
    current_grouped_results = current_grouped_results[:settings.top_k]

    # Compare stored vs current for change detection
    current_paths = set(r["metadata"].get("source_path", "") for r in current_grouped_results)
    current_details = {
        r["metadata"].get("source_path", ""): r["score"]
        for r in current_grouped_results
    }
    stored_paths = set(search_record.get("result_paths", []))
    stored_details = {
        item["path"]: item["score"]
        for item in search_record.get("result_details", [])
    }

    missing_paths = list(stored_paths - current_paths)
    new_paths = list(current_paths - stored_paths)

    score_changes = []
    for path in stored_paths & current_paths:
        old_score = stored_details.get(path, 0)
        new_score = current_details.get(path, 0)
        change = new_score - old_score
        score_changes.append({
            "path": path,
            "old_score": old_score,
            "new_score": new_score,
            "change": change,
        })
    score_changes.sort(key=lambda x: abs(x["change"]), reverse=True)

    return {
        "stored_result_count": search_record.get("result_count", 0),
        "current_result_count": len(current_grouped_results),
        "missing_files": missing_paths,
        "new_files": new_paths,
        "score_changes": score_changes,
        "results_changed": len(missing_paths) > 0 or len(new_paths) > 0 or len(score_changes) > 0,
    }


@router.get("/searches/{search_id}/versions")
@limiter.limit(STANDARD)
def get_search_versions(
    request: Request,
    search_id: str,
    searchdb: SearchDB = Depends(get_searchdb),
):
    """Get all versions of a search (original + re-queries)."""
    versions = searchdb.get_search_versions(search_id)
    if not versions:
        raise HTTPException(status_code=404, detail="Search not found")
    return {"versions": versions}


@router.patch("/searches/{search_id}")
@limiter.limit(STANDARD)
def rename_search(
    request: Request,
    search_id: str,
    req: RenameSearchRequest,
    searchdb: SearchDB = Depends(get_searchdb),
):
    """Rename a search's query text."""
    if not searchdb.rename_search(search_id, req.query):
        raise HTTPException(status_code=404, detail="Search not found")
    return {"status": "renamed"}


@router.delete("/searches/{search_id}")
@limiter.limit(STANDARD)
def delete_search(
    request: Request,
    search_id: str,
    searchdb: SearchDB = Depends(get_searchdb),
):
    """Delete a search from history."""
    searchdb.delete_search(search_id)
    return {"status": "deleted"}


@router.post("/search/summarize")
@limiter.limit(LLM)
def summarize_search(
    request: Request,
    req: SummarizeRequest,
    retriever: Retriever = Depends(get_retriever),
    searchdb: SearchDB = Depends(get_searchdb),
    scopedb: ScopeDB = Depends(get_scopedb),
    settings: Settings = Depends(get_settings),
    tracking: TrackingDB = Depends(get_tracking),
):
    """Generate AI summary of search results with streaming response."""
    cfg = _cfg(settings)
    ids = parse_scope_ids(req.scope_ids) or ([req.scope_id] if req.scope_id else None)
    scope_folders, scope_tags = resolve_scopes(ids, scopedb)
    allowed = resolve_tag_paths(scope_tags, req.ad_hoc_tags)
    top_k = req.top_k if req.top_k is not None else settings.top_k

    # Deep research mode — delegate to MCTS pipeline
    if req.deep_research and settings.core_enabled("deep_research"):
        from app.services.deep_research import stream_deep_research

        def deep_generate():
            kwargs = {}
            if req.deep_research_iterations is not None:
                kwargs["iterations"] = req.deep_research_iterations
            for event in stream_deep_research(
                req.query,
                retriever,
                settings,
                folders_filter=scope_folders or None,
                allowed_paths=allowed,
                **kwargs,
            ):
                # Intercept summary_text to persist, then forward as-is
                if req.search_id and "event: summary_text" in event:
                    import json as _json
                    try:
                        for line in event.strip().splitlines():
                            if line.startswith("data: "):
                                text = _json.loads(line[6:]).get("text", "")
                                if text:
                                    searchdb.update_summary(req.search_id, text)
                                    logger.info("Saved deep research summary for search %s", req.search_id)
                                break
                    except (ValueError, IndexError, KeyError) as e:
                        logger.warning(
                            "Could not extract summary_text from deep research SSE event: %s (raw: %s)",
                            e, event[:200],
                        )
                yield event

        return StreamingResponse(deep_generate(), media_type="text/event-stream")

    # Strip quotes for vector search, keep original for LLM prompt
    sum_phrases: list[str] = []
    if cfg["exact_phrase_matching"]:
        sum_phrases = [m.lower() for m in re.findall(r'"([^"]+)"', req.query)]
    sum_search_q = req.query.replace('"', '') if sum_phrases else req.query

    results = retriever.search(
        sum_search_q,
        top_k=top_k,
        folder_filter=req.folder,
        folders_filter=scope_folders or None,
        tag_filter=req.tag,
        allowed_paths=allowed,
    )

    # Post-filter for exact phrase matches
    if sum_phrases:
        results = [r for r in results if all(p in r.document.lower() for p in sum_phrases)]

    if not results:
        def empty():
            yield sse("token", {"content": "No relevant documents found for this query."})
            yield sse("done", {})
        return StreamingResponse(empty(), media_type="text/event-stream")

    documents = [r.document for r in results]
    metadatas = [r.metadata for r in results]
    context, _ = format_context(documents, metadatas)
    sources = extract_unique_sources(metadatas)

    messages = [
        {"role": "system", "content": settings.search_summary_prompt},
        {"role": "user", "content": get_search_summary_user().format(
            context=context, query=req.query,
        )},
    ]

    def generate():
        yield sse("sources", {"sources": sources})

        raw = ""
        last_yielded = ""
        try:
            for chunk in get_streaming_completion(messages, settings):
                raw += chunk
                cleaned = strip_thinking(raw)
                if cleaned != last_yielded:
                    delta = cleaned[len(last_yielded):]
                    if delta:
                        yield sse("token", {"content": delta})
                        last_yielded = cleaned
        except RuntimeError as e:
            logger.error("Summary LLM error: %s", e)
            yield sse("error", {"message": "LLM request failed. Check server logs for details."})

        # Save summary if search_id provided
        if req.search_id and last_yielded:
            searchdb.update_summary(req.search_id, last_yielded)
            logger.info("Saved summary for search %s", req.search_id)

        yield sse("done", {})

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/search/enhance-query")
@limiter.limit(LLM)
def enhance_query_endpoint(
    request: Request,
    req: SearchRequest,
    settings: Settings = Depends(get_settings),
):
    """
    Enhance a search query using LLM to extract keywords and expand acronyms.

    This endpoint can be used independently to enhance any query before searching.
    Returns enhanced query details or falls back gracefully if LLM is offline.
    """
    if not settings.intelligent_search_enabled:
        return {
            "enhanced": False,
            "original_query": req.query,
            "enhanced_query": req.query,
            "keywords": [],
            "expanded_terms": {},
            "context": "",
        }

    enhanced = enhance_query(req.query, settings)

    if enhanced.error:
        # LLM offline - return original query
        return {
            "enhanced": False,
            "original_query": req.query,
            "enhanced_query": req.query,
            "keywords": [],
            "expanded_terms": {},
            "context": "",
            "error": enhanced.error,
        }

    enhanced_query = build_enhanced_search_query(enhanced)

    return {
        "enhanced": True,
        "original_query": enhanced.original,
        "enhanced_query": enhanced_query,
        "keywords": enhanced.keywords,
        "expanded_terms": enhanced.expanded_terms,
        "context": enhanced.context,
    }
