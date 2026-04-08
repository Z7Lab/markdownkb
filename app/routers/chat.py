"""Chat endpoints (sync and streaming)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_chatdb, get_conversation_history, get_retriever, get_scopedb, get_settings, get_tracking
from app.rag.llm import get_completion
from app.rag.prompts import build_rag_messages
from app.rag.retriever import Retriever
from app.ratelimit import LLM, STANDARD, limiter
from app.schemas import ChatRequest, SavePlanRequest, StreamChatRequest
from app.scope_utils import parse_scope_ids, resolve_scopes
from app.tag_utils import resolve_tag_paths
from app.services.chat_service import (
    chat_respond,
    rewrite_query,
    save_last_response_as_plan,
)
from app.storage.chatdb import ChatDB
from app.storage.scopedb import ScopeDB
from app.storage.trackingdb import TrackingDB
from app.utils import short_title, sse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
@limiter.limit(LLM)
def chat(
    request: Request,
    req: ChatRequest,
    settings: Settings = Depends(get_settings),
    retriever: Retriever = Depends(get_retriever),
):
    search_query = rewrite_query(req.message, settings)
    results = retriever.search(search_query)
    if not results:
        return {
            "response": "No relevant information found.",
            "sources": [],
        }

    documents = [r.document for r in results]
    metadatas = [r.metadata for r in results]

    messages, source_map = build_rag_messages(
        req.message,
        documents,
        metadatas,
        conversation_history=req.conversation_history,
        system_prompt=settings.system_prompt,
    )

    try:
        response = get_completion(messages, settings)
    except RuntimeError as e:
        logger.error("LLM completion failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail="LLM provider request failed",
        ) from e

    sources = list(
        {m.get("source_path", "") for m in metadatas if m.get("source_path")}
    )

    return {"response": response, "sources": sources, "source_map": source_map}


@router.post("/chat/stream")
@limiter.limit(LLM)
def chat_stream(
    request: Request,
    req: StreamChatRequest,
    settings: Settings = Depends(get_settings),
    retriever: Retriever = Depends(get_retriever),
    chatdb: ChatDB = Depends(get_chatdb),
    scopedb: ScopeDB = Depends(get_scopedb),
    tracking: TrackingDB = Depends(get_tracking),
    conv_history=Depends(get_conversation_history),
):
    # Multi-scope: prefer scope_ids, fall back to single scope_id
    ids = parse_scope_ids(req.scope_ids) or ([req.scope_id] if req.scope_id else None)
    scope_folders, scope_tags, exclude_patterns = resolve_scopes(ids, scopedb)
    allowed = resolve_tag_paths(scope_tags, req.ad_hoc_tags)

    # Bucket-scoped chat: use a bucket-specific retriever
    bucket_retriever = None
    if req.bucket_id:
        bucket_service = getattr(request.app.state, "bucket_service", None)
        if bucket_service is None:
            raise HTTPException(status_code=503, detail="Buckets plugin not initialized")
        record = bucket_service.db.resolve(req.bucket_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Bucket not found: {req.bucket_id}")
        bucket_retriever = bucket_service._get_retriever(record["id"], settings)

    if req.thread_id:
        thread_id = req.thread_id
        title = ""
    else:
        title = short_title(req.message)
        thread_id = chatdb.create_thread(title)

    def generate():
        yield sse("thread", {"thread_id": thread_id, "title": title})

        sources: list[str] = []
        source_map: dict[str, str] = {}
        last_yielded = ""
        try:
            for partial in chat_respond(
                req.message,
                bucket_retriever or retriever,
                settings,
                chatdb=chatdb,
                thread_id=thread_id,
                folders_filter=scope_folders or None if not bucket_retriever else None,
                allowed_paths=allowed if not bucket_retriever else None,
                exclude_patterns=exclude_patterns if not bucket_retriever else None,
                sources_out=sources,
                source_map_out=source_map,
                conversation_history=conv_history,
            ):
                new_text = partial[len(last_yielded):]
                if new_text:
                    yield sse("token", {"content": new_text})
                    last_yielded = partial

            if sources:
                chatdb.set_sources(thread_id, "assistant", sources, source_map or None)
                yield sse("sources", {"sources": sources, "source_map": source_map})
        except (RuntimeError, OSError, ValueError) as e:
            logger.error("LLM/retrieval error during chat stream: %s", e)
            yield sse("error", {"message": "LLM request failed. Check server logs for details."})
        except Exception:
            logger.exception("Unexpected error during chat stream")
            yield sse("error", {"message": "An unexpected error occurred. Check server logs for details."})

        yield sse("done", {})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


@router.delete("/chat/history")
@limiter.limit(STANDARD)
def clear_history(
    request: Request,
    chatdb: ChatDB = Depends(get_chatdb),
    conv_history=Depends(get_conversation_history),
):
    conv_history.clear()
    chatdb.clear_all()
    return {"status": "cleared"}


@router.post("/chat/save-plan")
@limiter.limit(STANDARD)
def save_plan(
    request: Request,
    req: SavePlanRequest,
    settings: Settings = Depends(get_settings),
):
    result = save_last_response_as_plan(
        req.history,
        settings,
    )
    return {"message": result}
