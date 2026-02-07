"""Search endpoints with history and AI summary."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_retriever, get_searchdb, get_settings
from app.rag.llm import get_streaming_completion
from app.rag.prompts import SEARCH_SUMMARY_USER, format_context
from app.rag.retriever import Retriever
from app.ratelimit import HEAVY, LLM, STANDARD, limiter
from app.schemas import SearchRequest, SummarizeRequest
from app.services.chat_service import _strip_thinking, extract_unique_sources
from app.services.query_service import build_enhanced_search_query, enhance_query
from app.storage.searchdb import SearchDB
from app.utils import sse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search")
@limiter.limit(HEAVY)
def search(
    request: Request,
    req: SearchRequest,
    retriever: Retriever = Depends(get_retriever),
    searchdb: SearchDB = Depends(get_searchdb),
    settings: Settings = Depends(get_settings),
):
    """Search the vector database with optional intelligent query enhancement."""
    search_query = req.query
    llm_offline = False

    # Optionally enhance query with LLM
    if settings.intelligent_search_enabled:
        enhanced = enhance_query(req.query, settings)
        if enhanced.error:
            logger.warning("Intelligent search failed, using original query: %s", enhanced.error)
            llm_offline = True
        else:
            # Build enhanced query from LLM extraction
            search_query = build_enhanced_search_query(enhanced)
            logger.info("Enhanced query: %s -> %s", req.query, search_query)

    results = retriever.search(
        search_query,
        top_k=req.top_k,
        folder_filter=req.folder,
        tag_filter=req.tag,
    )

    # Extract result metadata for history preservation
    result_paths = [r.metadata.get("source_path", "") for r in results if r.metadata.get("source_path")]
    result_count = len(results)

    # Auto-save search to history with result metadata
    search_id = searchdb.save_search(
        req.query,
        req.folder,
        req.tag,
        result_paths=result_paths,
        result_count=result_count,
    )

    return {
        "results": [
            {
                "document": r.document,
                "metadata": r.metadata,
                "score": r.score,
            }
            for r in results
        ],
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
@limiter.limit(HEAVY)
def load_historical_search(
    request: Request,
    search_id: str,
    searchdb: SearchDB = Depends(get_searchdb),
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
):
    """
    Load a historical search and re-run it with current KB state.

    Returns:
    - Stored summary (preserved from original)
    - Current search results
    - Comparison data (missing/new files)
    - Original metadata (timestamp, result count)
    """
    search_record = searchdb.get_search(search_id)
    if not search_record:
        raise HTTPException(status_code=404, detail="Search not found")

    # Mark as viewed (updates last_viewed_at timestamp)
    searchdb.mark_viewed(search_id)

    # Re-run search with current KB state
    search_query = search_record["query"]

    # Apply intelligent search if enabled (same as original search)
    llm_offline = False
    if settings.intelligent_search_enabled:
        enhanced = enhance_query(search_record["query"], settings)
        if enhanced.error:
            logger.warning("Intelligent search failed, using original query: %s", enhanced.error)
            llm_offline = True
        else:
            search_query = build_enhanced_search_query(enhanced)
            logger.info("Enhanced query: %s -> %s", search_record["query"], search_query)

    current_results = retriever.search(
        search_query,
        top_k=settings.top_k,
        folder_filter=search_record.get("folder"),
        tag_filter=search_record.get("tag"),
    )

    # Extract current result paths
    current_paths = set(
        r.metadata.get("source_path", "")
        for r in current_results
        if r.metadata.get("source_path")
    )

    # Compare with stored results
    stored_paths = set(search_record.get("result_paths", []))
    missing_paths = list(stored_paths - current_paths)
    new_paths = list(current_paths - stored_paths)

    return {
        "results": [
            {
                "document": r.document,
                "metadata": r.metadata,
                "score": r.score,
            }
            for r in current_results
        ],
        "search_id": search_id,
        "query": search_record["query"],
        "folder": search_record.get("folder"),
        "tag": search_record.get("tag"),
        "summary": search_record.get("summary"),  # Preserved from original
        "created_at": search_record["created_at"],
        "is_historical": True,
        "stored_result_count": search_record.get("result_count", 0),
        "current_result_count": len(current_results),
        "missing_files": missing_paths,  # Files that were in original but not now
        "new_files": new_paths,  # Files that are new since original
        "results_changed": len(missing_paths) > 0 or len(new_paths) > 0,
        "llm_offline": llm_offline,
    }


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
    settings: Settings = Depends(get_settings),
):
    """Generate AI summary of search results with streaming response."""
    results = retriever.search(
        req.query,
        top_k=req.top_k,
        folder_filter=req.folder,
        tag_filter=req.tag,
    )

    if not results:
        def empty():
            yield sse("token", {"content": "No relevant documents found for this query."})
            yield sse("done", {})
        return StreamingResponse(empty(), media_type="text/event-stream")

    documents = [r.document for r in results]
    metadatas = [r.metadata for r in results]
    context = format_context(documents, metadatas)
    sources = extract_unique_sources(metadatas)

    messages = [
        {"role": "system", "content": settings.search_summary_prompt},
        {"role": "user", "content": SEARCH_SUMMARY_USER.format(
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
                cleaned = _strip_thinking(raw)
                if cleaned != last_yielded:
                    delta = cleaned[len(last_yielded):]
                    if delta:
                        yield sse("token", {"content": delta})
                        last_yielded = cleaned
        except RuntimeError as e:
            logger.error("Summary LLM error: %s", e)
            yield sse("token", {"content": f"\n\nError: {e}"})

        # Save summary if search_id provided
        if req.search_id and last_yielded:
            searchdb.update_summary(req.search_id, last_yielded)
            logger.info("Saved summary for search %s", req.search_id)

        yield sse("done", {})

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/folders")
@limiter.limit(STANDARD)
def get_folders(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    retriever: Retriever = Depends(get_retriever),
):
    """Get unique folder paths from indexed documents."""
    all_folders = retriever.get_unique_folders()
    total = len(all_folders)
    items = all_folders[offset:offset + limit]
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/tags")
@limiter.limit(STANDARD)
def get_tags(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    retriever: Retriever = Depends(get_retriever),
):
    """Get unique tags from indexed documents."""
    all_tags = retriever.get_unique_tags()
    total = len(all_tags)
    items = all_tags[offset:offset + limit]
    return {"items": items, "total": total, "offset": offset, "limit": limit}


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
