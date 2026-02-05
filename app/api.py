"""FastAPI REST endpoints for programmatic access to mdkb."""

import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import Settings
from app.ingestion.indexer import run_index
from app.rag.llm import get_completion
from app.rag.prompts import build_rag_messages
from app.rag.retriever import Retriever
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore
from app.ui.chat import conversation_history

logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    """Request body for semantic search."""
    query: str
    top_k: int = 5
    folder: str | None = None
    tag: str | None = None


class ChatRequest(BaseModel):
    """Request body for RAG chat."""
    message: str
    conversation_history: list[dict] | None = None


class AddSourceRequest(BaseModel):
    """Request body for adding a source directory."""
    path: str


class ExportRequest(BaseModel):
    """Request body for exporting conversations."""
    format: str = "json"


def create_api(
    settings: Settings,
    store: VectorStore,
    retriever: Retriever,
    tracking: TrackingDB,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    api = FastAPI(title="mdkb API", version="1.0.0")

    @api.get("/api/health")
    def health():
        return {"status": "ok", "chunks": store.count}

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
                status_code=502, detail=str(e)
            ) from e

        sources = list({
            m.get("source_path", "")
            for m in metadatas if m.get("source_path")
        })

        return {"response": response, "sources": sources}

    @api.post("/api/index")
    def index():
        result = run_index(settings, store, tracking)
        return {"message": result}

    @api.get("/api/sources")
    def get_sources():
        return {"sources": settings.sources}

    @api.post("/api/sources")
    def add_source(req: AddSourceRequest):
        settings.add_source(req.path)
        settings.save()
        return {"sources": settings.sources}

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

    @api.get("/api/files")
    def list_files():
        return {"files": tracking.get_all_files()}

    @api.get("/api/file")
    def read_file(path: str):
        p = Path(path)
        if not p.exists():
            raise HTTPException(
                status_code=404, detail="File not found"
            )
        try:
            content = p.read_text(
                encoding="utf-8", errors="replace"
            )
            return {"path": str(p), "content": content}
        except OSError as e:
            raise HTTPException(
                status_code=500, detail=str(e)
            ) from e

    @api.get("/api/folders")
    def get_folders():
        return {"folders": retriever.get_unique_folders()}

    @api.get("/api/tags")
    def get_tags():
        return {"tags": retriever.get_unique_tags()}

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
