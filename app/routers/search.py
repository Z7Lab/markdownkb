"""Search endpoints with history and AI summary."""

import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_retriever, get_searchdb, get_settings
from app.rag.llm import get_streaming_completion
from app.rag.prompts import (
    SEARCH_SUMMARY_SYSTEM,
    SEARCH_SUMMARY_USER,
    format_context,
)
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

    # Auto-save search to history
    search_id = searchdb.save_search(req.query, req.folder, req.tag)

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
    }


@router.get("/searches")
@limiter.limit(STANDARD)
def list_searches(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    searchdb: SearchDB = Depends(get_searchdb),
):
    items = searchdb.list_searches(offset=offset, limit=limit)
    total = searchdb.search_count()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.delete("/searches/{search_id}")
@limiter.limit(STANDARD)
def delete_search(
    request: Request,
    search_id: str,
    searchdb: SearchDB = Depends(get_searchdb),
):
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
