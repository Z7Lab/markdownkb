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
):
    results = retriever.search(
        req.query,
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
        {"role": "system", "content": SEARCH_SUMMARY_SYSTEM},
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
