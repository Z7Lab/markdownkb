"""Chat endpoints (sync and streaming)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_chatdb, get_retriever, get_scopedb, get_settings
from app.rag.llm import get_completion
from app.rag.prompts import build_rag_messages
from app.rag.retriever import Retriever
from app.ratelimit import LLM, STANDARD, limiter
from app.schemas import ChatRequest, SavePlanRequest, StreamChatRequest
from app.services.chat_service import (
    chat_respond,
    conversation_history,
    extract_unique_sources,
    rewrite_query,
    save_last_response_as_plan,
)
from app.storage.chatdb import ChatDB
from app.storage.scopedb import ScopeDB
from app.utils import short_title, sse


def _resolve_scope(scope_id: str | None, scopedb: ScopeDB) -> dict | None:
    """Resolve a scope_id to its folders and tags, or None if no scope."""
    if not scope_id:
        return None
    scope = scopedb.get(scope_id)
    if not scope:
        raise HTTPException(status_code=404, detail="Scope not found")
    return {"folders": scope["folders"], "tags": scope["tags"]}

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

    messages = build_rag_messages(
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

    return {"response": response, "sources": sources}


@router.post("/chat/stream")
@limiter.limit(LLM)
def chat_stream(
    request: Request,
    req: StreamChatRequest,
    settings: Settings = Depends(get_settings),
    retriever: Retriever = Depends(get_retriever),
    chatdb: ChatDB = Depends(get_chatdb),
    scopedb: ScopeDB = Depends(get_scopedb),
):
    resolved = _resolve_scope(req.scope_id, scopedb)
    scope_folders = resolved["folders"] if resolved else None
    scope_tags = resolved["tags"] if resolved else None

    if req.thread_id:
        thread_id = req.thread_id
        title = ""
    else:
        title = short_title(req.message)
        thread_id = chatdb.create_thread(title)

    def generate():
        yield sse("thread", {"thread_id": thread_id, "title": title})

        last_yielded = ""
        for partial in chat_respond(
            req.message,
            retriever,
            settings,
            chatdb=chatdb,
            thread_id=thread_id,
            folders_filter=scope_folders or None,
            scope_tags=scope_tags or None,
        ):
            new_text = partial[len(last_yielded):]
            if new_text:
                yield sse("token", {"content": new_text})
                last_yielded = partial

        # Extract sources from the final response
        results = retriever.search(
            req.message,
            folders_filter=scope_folders or None,
            scope_tags=scope_tags or None,
        )
        if results:
            metadatas = [r.metadata for r in results]
            sources = extract_unique_sources(metadatas)
            if sources:
                chatdb.set_sources(thread_id, "assistant", sources)
                yield sse("sources", {"sources": sources})

        yield sse("done", {})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


@router.delete("/chat/history")
@limiter.limit(STANDARD)
def clear_history(request: Request):
    conversation_history.clear()
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
