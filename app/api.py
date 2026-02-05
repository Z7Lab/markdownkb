"""FastAPI REST endpoints for mdkb."""

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import Settings
from app.ingestion.indexer import reindex_file, run_index
from app.rag.llm import get_completion
from app.rag.prompts import build_rag_messages
from app.rag.retriever import Retriever
from app.services.chat_service import (
    chat_respond,
    conversation_history,
    extract_unique_sources,
    save_last_response_as_plan,
)
from app.services.llm_service import (
    build_model_list,
    get_model_capabilities,
    ping_model,
    stream_test_prompt,
    test_llm_connection,
)
from app.storage.chatdb import ChatDB
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)


# ── Request/Response models ──────────────────────────────────


class SearchRequest(BaseModel):
    """Request model for search API endpoint."""

    query: str
    top_k: int = 5
    folder: str | None = None
    tag: str | None = None


class ChatRequest(BaseModel):
    """Request model for chat API endpoint."""

    message: str
    conversation_history: list[dict] | None = None


class StreamChatRequest(BaseModel):
    """Request model for streaming chat API endpoint."""

    message: str
    thread_id: str | None = None


class AddSourceRequest(BaseModel):
    """Request model for adding a source."""

    path: str


class RemoveSourceRequest(BaseModel):
    """Request model for removing a source."""

    path: str


class FilePathRequest(BaseModel):
    """Request model for file path operations."""

    path: str


class SavePlanRequest(BaseModel):
    """Request model for saving conversation plan."""

    history: list[dict]


class ProviderSettingsRequest(BaseModel):
    """Request model for provider settings."""

    name: str
    model: str
    api_base: str = ""


class TestConnectionRequest(BaseModel):
    """Request model for testing LLM connection."""

    name: str
    model: str
    api_base: str = ""


class RefreshModelsRequest(BaseModel):
    """Request model for refreshing available models."""

    name: str
    api_base: str


class FeatureToggleRequest(BaseModel):
    """Request model for toggling feature flags."""

    name: str
    enabled: bool


class TestPromptRequest(BaseModel):
    """Request model for testing prompt with LLM."""

    prompt: str
    provider: str = ""
    model: str = ""
    api_base: str = ""


class ModelInfoRequest(BaseModel):
    """Request model for getting model capabilities."""

    model: str
    api_base: str = ""


class RenameThreadRequest(BaseModel):
    """Request model for renaming conversation thread."""

    title: str


class ExportRequest(BaseModel):
    """Request model for exporting conversation history."""

    format: str = "json"


# ── API factory ──────────────────────────────────────────────


def create_api(
    settings: Settings,
    store: VectorStore,
    retriever: Retriever,
    tracking: TrackingDB,
    chatdb: ChatDB,
    cancel_event: threading.Event,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    api = FastAPI(title="mdkb API", version="1.0.0")

    api.add_middleware(
        CORSMiddleware,
        allow_origins=[
            f"http://localhost:{os.environ.get('FRONTEND_PORT', '9714')}",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health / Stats ───────────────────────────────────

    @api.get("/api/health")
    def health():
        return {"status": "ok", "chunks": store.count}

    @api.get("/api/stats")
    def stats():
        db_stats = tracking.get_stats()
        return {
            "sources": settings.sources,
            "files_tracked": db_stats["total_files"],
            "files_complete": db_stats["complete"],
            "files_error": db_stats["error"],
            "chunks_indexed": store.count,
            "embedding_model": settings.embedding_model,
            "active_provider": settings.active_provider,
        }

    # ── Search ───────────────────────────────────────────

    @api.post("/api/search")
    def search(req: SearchRequest):
        results = retriever.search(
            req.query,
            top_k=req.top_k,
            folder_filter=req.folder,
            tag_filter=req.tag,
        )
        return {
            "results": [
                {
                    "document": r.document,
                    "metadata": r.metadata,
                    "score": r.score,
                }
                for r in results
            ]
        }

    @api.get("/api/folders")
    def get_folders():
        return {"folders": retriever.get_unique_folders()}

    @api.get("/api/tags")
    def get_tags():
        return {"tags": retriever.get_unique_tags()}

    # ── Chat ─────────────────────────────────────────────

    @api.post("/api/chat")
    def chat(req: ChatRequest):
        results = retriever.search(req.message)
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
        )

        try:
            response = get_completion(messages, settings)
        except RuntimeError as e:
            raise HTTPException(
                status_code=502,
                detail=str(e),
            ) from e

        sources = list(
            {m.get("source_path", "") for m in metadatas if m.get("source_path")}
        )

        return {"response": response, "sources": sources}

    @api.post("/api/chat/stream")
    def chat_stream(req: StreamChatRequest):
        if req.thread_id:
            thread_id = req.thread_id
            title = ""
        else:
            title = _short_title(req.message)
            thread_id = chatdb.create_thread(title)

        def generate():
            yield _sse("thread", {"thread_id": thread_id, "title": title})

            last_yielded = ""
            for partial in chat_respond(
                req.message,
                retriever,
                settings,
                chatdb=chatdb,
                thread_id=thread_id,
            ):
                new_text = partial[len(last_yielded) :]
                if new_text:
                    yield _sse("token", {"content": new_text})
                    last_yielded = partial

            # Extract sources from the final response
            results = retriever.search(req.message)
            if results:
                metadatas = [r.metadata for r in results]
                sources = extract_unique_sources(metadatas)
                if sources:
                    yield _sse("sources", {"sources": sources})

            yield _sse("done", {})

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )

    @api.delete("/api/chat/history")
    def clear_history():
        conversation_history.clear()
        return {"status": "cleared"}

    @api.post("/api/chat/save-plan")
    def save_plan(req: SavePlanRequest):
        result = save_last_response_as_plan(
            req.history,
            settings,
        )
        return {"message": result}

    # ── Threads ──────────────────────────────────────────

    @api.get("/api/threads")
    def list_threads():
        return {"threads": chatdb.list_threads()}

    @api.get("/api/threads/{thread_id}/messages")
    def get_thread_messages(thread_id: str):
        if not chatdb.get_thread(thread_id):
            raise HTTPException(status_code=404, detail="Thread not found")
        return {"messages": chatdb.get_messages(thread_id)}

    @api.delete("/api/threads/{thread_id}")
    def delete_thread(thread_id: str):
        if not chatdb.get_thread(thread_id):
            raise HTTPException(status_code=404, detail="Thread not found")
        chatdb.delete_thread(thread_id)
        return {"status": "deleted"}

    @api.patch("/api/threads/{thread_id}")
    def rename_thread(thread_id: str, req: RenameThreadRequest):
        if not chatdb.get_thread(thread_id):
            raise HTTPException(status_code=404, detail="Thread not found")
        chatdb.rename_thread(thread_id, req.title)
        return {"status": "renamed"}

    # ── Files / Browse ───────────────────────────────────

    @api.get("/api/files")
    def list_files():
        # Prune files that no longer exist on disk
        all_files = tracking.get_all_files()
        existing_paths = {f["path"] for f in all_files if Path(f["path"]).exists()}
        removed = tracking.remove_files_not_in(existing_paths)
        for path in removed:
            store.delete_by_source(path)
            logger.info("Pruned missing file: %s", path)
        # Return the pruned list
        return {"files": tracking.get_all_files()}

    @api.get("/api/file")
    def read_file(path: str):
        p = Path(path)
        if not p.exists():
            raise HTTPException(
                status_code=404,
                detail="File not found",
            )
        try:
            content = p.read_text(
                encoding="utf-8",
                errors="replace",
            )
            return {"path": str(p), "content": content}
        except OSError as e:
            raise HTTPException(
                status_code=500,
                detail=str(e),
            ) from e

    @api.post("/api/files/exclude")
    def exclude_file(req: FilePathRequest):
        record = tracking.get_file(req.path)
        if not record:
            raise HTTPException(
                status_code=404,
                detail="File not tracked",
            )
        tracking.exclude_file(req.path)
        store.delete_by_source(req.path)
        return {
            "status": "excluded",
            "chunks_removed": record["chunk_count"],
        }

    @api.post("/api/files/include")
    def include_file(req: FilePathRequest):
        record = tracking.get_file(req.path)
        if not record:
            raise HTTPException(
                status_code=404,
                detail="File not tracked",
            )
        tracking.include_file(req.path)
        result = reindex_file(
            req.path,
            settings,
            store,
            tracking,
        )
        return {"status": "included", "message": result}

    # ── Sources ──────────────────────────────────────────

    @api.get("/api/sources")
    def get_sources():
        return {"sources": settings.sources}

    @api.post("/api/sources")
    def add_source(req: AddSourceRequest):
        settings.add_source(req.path)
        settings.save()
        return {"sources": settings.sources}

    @api.delete("/api/sources")
    def remove_source(req: RemoveSourceRequest):
        settings.remove_source(req.path)
        settings.save()
        return {"sources": settings.sources}

    # ── Settings ─────────────────────────────────────────

    @api.get("/api/settings")
    def get_settings():
        active_cfg = settings.get_active_llm_config()
        return {
            "active_provider": settings.active_provider,
            "providers": [
                {
                    "name": p["name"],
                    "model": p.get("model", ""),
                    "api_base": p.get("api_base", ""),
                }
                for p in settings.llm_providers
            ],
            "features": settings.features,
            "sources": settings.sources,
            "active_model": active_cfg.get("model", ""),
            "active_api_base": active_cfg.get("api_base", ""),
        }

    @api.put("/api/settings/provider")
    def save_provider(req: ProviderSettingsRequest):
        settings.active_provider = req.name
        for p in settings.llm_providers:
            if p.get("name") == req.name:
                p["model"] = req.model
                p["api_base"] = req.api_base
                break
        settings.save()
        return {"status": "saved"}

    @api.post("/api/settings/test-connection")
    def test_connection(req: TestConnectionRequest):
        result = test_llm_connection(
            req.name,
            req.model,
            req.api_base,
        )
        return {"result": result}

    @api.post("/api/settings/ping-model")
    def ping_model_endpoint(req: TestConnectionRequest):
        result = ping_model(req.model, req.api_base)
        return {"result": result}

    @api.post("/api/settings/refresh-models")
    def refresh_models(req: RefreshModelsRequest):
        models, status = build_model_list(
            req.name,
            req.api_base,
        )
        return {"models": models, "status": status}

    @api.post("/api/settings/test-prompt")
    def test_prompt(req: TestPromptRequest):
        if req.provider and req.model:
            model = req.model
            api_base = req.api_base or ""
        else:
            active = settings.get_active_llm_config()
            model = active.get("model", "")
            api_base = active.get("api_base", "") or ""

        if not model:
            raise HTTPException(status_code=400, detail="No model configured")

        def generate():
            try:
                for event, data in stream_test_prompt(
                    req.prompt,
                    model,
                    api_base,
                    settings.llm_temperature,
                    settings.llm_max_tokens,
                ):
                    yield _sse(event, data)
            except (RuntimeError, ConnectionError, TimeoutError) as e:
                yield _sse("error", {"message": str(e)})

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )

    @api.post("/api/settings/model-info")
    def model_info(req: ModelInfoRequest):
        return get_model_capabilities(req.model, req.api_base)

    @api.put("/api/settings/features")
    def toggle_feature(req: FeatureToggleRequest):
        settings.features[req.name] = req.enabled
        settings.save()
        return {"status": "saved"}

    # ── Indexing ─────────────────────────────────────────

    @api.post("/api/index")
    def index():
        cancel_event.clear()
        result = run_index(
            settings,
            store,
            tracking,
            cancel=cancel_event,
        )
        return {"message": result}

    @api.post("/api/index/cancel")
    def cancel_index():
        cancel_event.set()
        return {"status": "cancelling"}

    # ── Export ────────────────────────────────────────────

    @api.post("/api/export")
    def export_conversations(req: ExportRequest):
        history = conversation_history.get_history()
        if req.format == "markdown":
            lines = ["# mdkb Conversation Export\n"]
            lines.append(f"*Exported: {datetime.now().isoformat()}*" "\n\n---\n")
            for msg in history:
                role = msg["role"].capitalize()
                lines.append(f"**{role}:** {msg['content']}\n\n")
            return {
                "content": "\n".join(lines),
                "format": "markdown",
            }
        return {
            "content": history,
            "format": "json",
            "exported_at": datetime.now().isoformat(),
        }

    return api


def _sse(event: str, data: dict) -> str:
    """Format a server-sent event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _short_title(message: str, limit: int = 50) -> str:
    """Derive a short thread title from the first user message."""
    text = message.strip().split("\n")[0]
    # Take first sentence if there's punctuation
    for ch in ".?!":
        idx = text.find(ch)
        if 0 < idx < limit:
            return text[: idx + 1]
    # Otherwise truncate at word boundary
    if len(text) <= limit:
        return text
    cut = text[:limit].rfind(" ")
    if cut > 20:
        return text[:cut] + "..."
    return text[:limit] + "..."
