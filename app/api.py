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
    test_llm_connection,
)
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)


# ── Request/Response models ──────────────────────────────────


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    folder: str | None = None
    tag: str | None = None


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] | None = None


class StreamChatRequest(BaseModel):
    message: str


class AddSourceRequest(BaseModel):
    path: str


class RemoveSourceRequest(BaseModel):
    path: str


class FilePathRequest(BaseModel):
    path: str


class SavePlanRequest(BaseModel):
    history: list[dict]


class ProviderSettingsRequest(BaseModel):
    name: str
    model: str
    api_base: str = ""


class TestConnectionRequest(BaseModel):
    name: str
    model: str
    api_base: str = ""


class RefreshModelsRequest(BaseModel):
    name: str
    api_base: str


class FeatureToggleRequest(BaseModel):
    name: str
    enabled: bool


class ExportRequest(BaseModel):
    format: str = "json"


# ── API factory ──────────────────────────────────────────────


def create_api(
    settings: Settings,
    store: VectorStore,
    retriever: Retriever,
    tracking: TrackingDB,
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
            req.query, top_k=req.top_k,
            folder_filter=req.folder, tag_filter=req.tag,
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
            req.message, documents, metadatas,
            conversation_history=req.conversation_history,
        )

        try:
            response = get_completion(messages, settings)
        except RuntimeError as e:
            raise HTTPException(
                status_code=502, detail=str(e),
            ) from e

        sources = list({
            m.get("source_path", "")
            for m in metadatas if m.get("source_path")
        })

        return {"response": response, "sources": sources}

    @api.post("/api/chat/stream")
    def chat_stream(req: StreamChatRequest):
        def generate():
            last_yielded = ""
            sources = []
            for partial in chat_respond(
                req.message, retriever, settings,
            ):
                new_text = partial[len(last_yielded):]
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
            generate(), media_type="text/event-stream",
        )

    @api.delete("/api/chat/history")
    def clear_history():
        conversation_history.clear()
        return {"status": "cleared"}

    @api.post("/api/chat/save-plan")
    def save_plan(req: SavePlanRequest):
        result = save_last_response_as_plan(
            req.history, settings,
        )
        return {"message": result}

    # ── Files / Browse ───────────────────────────────────

    @api.get("/api/files")
    def list_files():
        return {"files": tracking.get_all_files()}

    @api.get("/api/file")
    def read_file(path: str):
        p = Path(path)
        if not p.exists():
            raise HTTPException(
                status_code=404, detail="File not found",
            )
        try:
            content = p.read_text(
                encoding="utf-8", errors="replace",
            )
            return {"path": str(p), "content": content}
        except OSError as e:
            raise HTTPException(
                status_code=500, detail=str(e),
            ) from e

    @api.post("/api/files/exclude")
    def exclude_file(req: FilePathRequest):
        record = tracking.get_file(req.path)
        if not record:
            raise HTTPException(
                status_code=404, detail="File not tracked",
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
                status_code=404, detail="File not tracked",
            )
        tracking.include_file(req.path)
        result = reindex_file(
            req.path, settings, store, tracking,
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
            req.name, req.model, req.api_base,
        )
        return {"result": result}

    @api.post("/api/settings/refresh-models")
    def refresh_models(req: RefreshModelsRequest):
        models, status = build_model_list(
            req.name, req.api_base,
        )
        return {"models": models, "status": status}

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
            settings, store, tracking, cancel=cancel_event,
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
            lines.append(
                f"*Exported: {datetime.now().isoformat()}*"
                "\n\n---\n"
            )
            for msg in history:
                role = msg["role"].capitalize()
                lines.append(
                    f"**{role}:** {msg['content']}\n\n"
                )
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
