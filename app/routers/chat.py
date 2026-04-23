"""Chat endpoints (sync and streaming)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_chatdb, get_conversation_history, get_retriever, get_scopedb, get_settings, get_tracking
from app.rag.retriever import Retriever
from app.ratelimit import LLM, STANDARD, limiter
from app.schemas import ChatRequest, SavePlanRequest, StreamChatRequest
from app.scope_utils import parse_scope_ids, resolve_scopes
from app.tag_utils import resolve_tag_paths
from app.services.chat_service import (
    chat_respond,
    resolve_chat_scope,
    save_last_response_as_plan,
)
from app.storage.chatdb import ChatDB
from app.storage.scopedb import ScopeDB
from app.storage.trackingdb import TrackingDB
from app.utils import short_title, sse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat")
@limiter.limit(LLM)
def chat(
    request: Request,
    req: ChatRequest,
    settings: Settings = Depends(get_settings),
    retriever: Retriever = Depends(get_retriever),
):
    sources: list[str] = []
    source_map: dict[str, str] = {}
    response = ""
    try:
        for chunk in chat_respond(
            req.message,
            retriever,
            settings,
            history_override=req.conversation_history,
            sources_out=sources,
            source_map_out=source_map,
        ):
            response = chunk
    except RuntimeError as e:
        logger.error("LLM completion failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail="LLM provider request failed",
        ) from e

    if not response:
        return {"response": "No relevant information found.", "sources": []}
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
    chat_scope = resolve_chat_scope(
        app_state=request.app.state,
        scope_ids=req.scope_ids,
        scope_id=req.scope_id,
        bucket_ids=req.bucket_ids,
        ad_hoc_tags=req.ad_hoc_tags,
        settings=settings,
        scopedb=scopedb,
    )
    scope_folders = chat_scope.scope_folders
    allowed = chat_scope.allowed_paths
    exclude_patterns = chat_scope.exclude_patterns
    bucket_retrievers = chat_scope.bucket_retrievers

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
        # Retrieval mode (computed once by resolve_chat_scope):
        # - bucket only (no scope): use bucket retriever, no filters
        # - scope only (no bucket): use main retriever with scope filters
        # - both: use main retriever with scope filters + bucket retrievers merged
        bucket_only = chat_scope.bucket_only

        bucket_allowed_paths = set(req.bucket_file_paths) if req.bucket_file_paths else None

        inner = chat_respond(
            req.message,
            bucket_retrievers[0] if bucket_only else retriever,
            settings,
            chatdb=chatdb,
            thread_id=thread_id,
            folders_filter=scope_folders if not bucket_only else None,
            allowed_paths=(allowed if not bucket_only else bucket_allowed_paths),
            exclude_patterns=exclude_patterns if not bucket_only else None,
            bucket_retrievers=(bucket_retrievers[1:] if bucket_only else bucket_retrievers) or None,
            bucket_allowed_paths=bucket_allowed_paths,
            sources_out=sources,
            source_map_out=source_map,
            conversation_history=conv_history,
            kgdb=getattr(request.app.state, "kgdb", None),
        )
        try:
            try:
                for partial in inner:
                    new_text = partial[len(last_yielded):]
                    if new_text:
                        yield sse("token", {"content": new_text})
                        last_yielded = partial

                if sources:
                    chatdb.set_sources(thread_id, "assistant", sources, source_map or None)
                    yield sse("sources", {"sources": sources, "source_map": source_map})
            except GeneratorExit:
                # Client disconnected mid-stream — close the inner generator so
                # the LLM call stops producing tokens the caller can no longer
                # see. Without this, generation continues and wastes quota.
                logger.info("Client disconnected from chat stream %s", thread_id)
                try:
                    inner.close()
                except Exception:
                    logger.debug("Inner generator close raised", exc_info=True)
                raise
            except (RuntimeError, OSError, ValueError) as e:
                logger.error("LLM/retrieval error during chat stream: %s", e)
                yield sse("error", {"message": "LLM request failed. Check server logs for details."})
            except Exception:
                logger.exception("Unexpected error during chat stream")
                yield sse("error", {"message": "An unexpected error occurred. Check server logs for details."})
        finally:
            # Make sure the inner generator is closed even on normal exit.
            try:
                inner.close()
            except Exception:
                pass

        active_cfg = settings.get_active_llm_config()
        yield sse("done", {
            "provider": settings.active_provider,
            "model": active_cfg.get("model", ""),
        })

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
