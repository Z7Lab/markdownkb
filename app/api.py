import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import Settings
from app.embeddings.embedder import embed_query, embed_texts
from app.ingestion.parser import parse_and_chunk
from app.ingestion.scanner import scan_sources
from app.rag.llm import get_completion
from app.rag.prompts import build_rag_messages
from app.rag.retriever import Retriever
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    folder: str | None = None
    tag: str | None = None


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] | None = None


class AddSourceRequest(BaseModel):
    path: str


class ExportRequest(BaseModel):
    format: str = "json"  # json or markdown


def create_api(settings: Settings, store: VectorStore,
               retriever: Retriever) -> FastAPI:
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
            return {"response": "No relevant information found.", "sources": []}

        documents = [r.document for r in results]
        metadatas = [r.metadata for r in results]

        messages = build_rag_messages(
            req.message, documents, metadatas,
            conversation_history=req.conversation_history,
        )

        try:
            response = get_completion(messages, settings)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))

        sources = list({m.get("source_path", "") for m in metadatas if m.get("source_path")})

        return {"response": response, "sources": sources}

    @api.post("/api/index")
    def index():
        files = scan_sources(settings.sources, settings.global_ignore)
        all_chunks = []
        for fi in files:
            chunks = parse_and_chunk(
                fi.path, fi.source_root,
                settings.chunk_size, settings.chunk_overlap,
            )
            all_chunks.extend(chunks)

        if not all_chunks:
            return {"message": "No files to index", "chunks": 0}

        texts = [c.content for c in all_chunks]
        embeddings = embed_texts(texts, settings.embedding_model)
        ids = [c.chunk_id for c in all_chunks]
        metadatas = [c.metadata for c in all_chunks]
        store.add(ids, texts, embeddings, metadatas)

        return {"message": "Index complete", "files": len(files),
                "chunks": len(all_chunks)}

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
        files = scan_sources(settings.sources, settings.global_ignore)
        return {
            "sources": settings.sources,
            "files_found": len(files),
            "chunks_indexed": store.count,
            "embedding_model": settings.embedding_model,
            "active_provider": settings.active_provider,
        }

    @api.get("/api/files")
    def list_files():
        sources = retriever.get_unique_sources()
        return {"files": sources}

    @api.get("/api/file")
    def read_file(path: str):
        p = Path(path)
        if not p.exists():
            raise HTTPException(status_code=404, detail="File not found")
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            return {"path": str(p), "content": content}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api.get("/api/folders")
    def get_folders():
        return {"folders": retriever.get_unique_folders()}

    @api.get("/api/tags")
    def get_tags():
        return {"tags": retriever.get_unique_tags()}

    @api.post("/api/export")
    def export_conversations(req: ExportRequest):
        from app.ui.chat import _conversation_history
        if req.format == "markdown":
            lines = ["# mdkb Conversation Export\n"]
            lines.append(f"*Exported: {datetime.now().isoformat()}*\n\n---\n")
            for msg in _conversation_history:
                role = msg["role"].capitalize()
                lines.append(f"**{role}:** {msg['content']}\n\n")
            return {"content": "\n".join(lines), "format": "markdown"}
        else:
            return {
                "content": _conversation_history,
                "format": "json",
                "exported_at": datetime.now().isoformat(),
            }

    return api
