"""Bucket management endpoints — CRUD, search, and chat."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_settings
from app.ratelimit import LLM, STANDARD, limiter

from .bucket_service import BucketService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["buckets"])


# -- Request schemas ---------------------------------------------------------

class BucketSource(BaseModel):
    path: str = Field(..., min_length=1)
    glob: str = Field("**/*.md")


class CreateBucketRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sources: list[BucketSource] = Field(default_factory=list)
    expires_in: int | None = Field(None, ge=60, description="Seconds until auto-delete")


class BucketSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(5, ge=1, le=50)


class BucketChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class AddToBucketRequest(BaseModel):
    sources: list[BucketSource] = Field(..., min_length=1)


class BucketDocument(BaseModel):
    name: str = Field(..., min_length=1, max_length=500, description="Virtual filename (e.g. 'notes.md')")
    content: str = Field(..., min_length=1, max_length=500000, description="Raw markdown content")


class PushDocumentsRequest(BaseModel):
    documents: list[BucketDocument] = Field(..., min_length=1, max_length=50)


class UpdateBucketRequest(BaseModel):
    expires_in: int | None = Field(None, description="Seconds from now, or null for permanent")


# -- Helpers -----------------------------------------------------------------

def _get_bucket_service(request: Request) -> BucketService:
    svc = getattr(request.app.state, "bucket_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Buckets plugin not initialized")
    return svc


# -- Endpoints ---------------------------------------------------------------

@router.get("/buckets")
@limiter.limit(STANDARD)
def list_buckets(
    request: Request,
    svc: BucketService = Depends(_get_bucket_service),
):
    """List all buckets with metadata and indexing status."""
    svc.cleanup_expired()
    buckets = svc.db.list_all()
    # Add indexing status by comparing DB chunk count vs ChromaDB
    for b in buckets:
        store = svc.get_store(b["id"])
        actual = store.count
        b["indexed_chunks"] = actual
        b["indexing"] = b["chunk_count"] > 0 and actual == 0
    return {"buckets": buckets}


@router.post("/buckets")
@limiter.limit(STANDARD)
def create_bucket(
    request: Request,
    req: CreateBucketRequest,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Create a new bucket from source paths."""
    try:
        sources = [s.model_dump() for s in req.sources]
        record = svc.create(req.name, sources, req.expires_in)
        return record
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("Bucket creation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Bucket creation failed")


@router.get("/buckets/{bucket_id}")
@limiter.limit(STANDARD)
def get_bucket(
    request: Request,
    bucket_id: str,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Get a single bucket by ID or name."""
    record = svc.db.resolve(bucket_id)
    if not record:
        raise HTTPException(status_code=404, detail="Bucket not found")
    return record


@router.patch("/buckets/{bucket_id}")
@limiter.limit(STANDARD)
def update_bucket(
    request: Request,
    bucket_id: str,
    req: UpdateBucketRequest,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Update bucket settings (expiration)."""
    record = svc.db.resolve(bucket_id)
    if not record:
        raise HTTPException(status_code=404, detail="Bucket not found")

    from datetime import datetime, timedelta, timezone
    if req.expires_in is None:
        expires_at = None
    elif req.expires_in <= 0:
        expires_at = None
    else:
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=req.expires_in)).strftime("%Y-%m-%d %H:%M:%S")

    svc.db.update_expiration(record["id"], expires_at)
    return {"status": "updated", "expires_at": expires_at}


@router.get("/buckets/{bucket_id}/files")
@limiter.limit(STANDARD)
def list_bucket_files(
    request: Request,
    bucket_id: str,
    svc: BucketService = Depends(_get_bucket_service),
):
    """List files in a bucket with chunk counts.

    Falls back to scanning source paths when ChromaDB is still
    being populated (background indexing).
    """
    record = svc.db.resolve(bucket_id)
    if not record:
        raise HTTPException(status_code=404, detail="Bucket not found")
    store = svc.get_store(record["id"])
    all_meta = store.get_all_metadatas()

    indexing = False
    if all_meta:
        # Group by source_path from ChromaDB
        files: dict[str, dict] = {}
        for meta in all_meta:
            path = meta.get("source_path", "")
            if not path:
                continue
            if path not in files:
                files[path] = {
                    "path": path,
                    "title": meta.get("title", ""),
                    "chunk_count": 0,
                }
            files[path]["chunk_count"] += 1
        file_list = sorted(files.values(), key=lambda f: f["path"])
    else:
        # ChromaDB empty — scan source paths to show files during indexing
        indexing = record["chunk_count"] > 0
        import json
        from pathlib import Path
        sources = json.loads(record.get("sources", "[]"))
        file_list = []
        for src in sources:
            path = src.get("path", "")
            glob_pattern = src.get("glob", "**/*.md")
            resolved = Path(path).resolve()
            if resolved.is_file() and resolved.suffix == ".md":
                file_list.append({"path": str(resolved), "title": "", "chunk_count": 0})
            elif resolved.is_dir():
                for match in sorted(resolved.glob(glob_pattern)):
                    if match.is_file() and match.suffix == ".md":
                        file_list.append({"path": str(match), "title": "", "chunk_count": 0})

    return {"files": file_list, "total": len(file_list), "indexing": indexing}


@router.get("/buckets/{bucket_id}/file")
@limiter.limit(STANDARD)
def read_bucket_file(
    request: Request,
    bucket_id: str,
    path: str,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Read a file's full content from a bucket.

    Reconstructs the document from stored chunks, ordered by chunk_index.
    Works for both filesystem-sourced and pushed (virtual) documents.
    """
    record = svc.db.resolve(bucket_id)
    if not record:
        raise HTTPException(status_code=404, detail="Bucket not found")
    store = svc.get_store(record["id"])
    result = store._collection.get(
        where={"source_path": path},
        include=["documents", "metadatas"],
    )
    if not result["ids"]:
        raise HTTPException(status_code=404, detail=f"File not found in bucket: {path}")

    # Sort by chunk_index and reconstruct
    chunks = sorted(
        zip(result["documents"], result["metadatas"]),
        key=lambda x: x[1].get("chunk_index", 0),
    )

    # Strip breadcrumb prefix from each chunk to get clean content
    parts = []
    for doc, _meta in chunks:
        lines = doc.split("\n", 2)
        if lines[0].startswith("From:") and len(lines) > 2:
            parts.append(lines[2])
        else:
            parts.append(doc)

    title = chunks[0][1].get("title", "") if chunks else ""

    return {
        "path": path,
        "title": title,
        "content": "\n\n".join(parts),
        "chunk_count": len(chunks),
    }


@router.delete("/buckets/{bucket_id}")
@limiter.limit(STANDARD)
def delete_bucket(
    request: Request,
    bucket_id: str,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Delete a bucket and its vector data."""
    try:
        result = svc.delete(bucket_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/buckets/{bucket_id}/search")
@limiter.limit(STANDARD)
def search_bucket(
    request: Request,
    bucket_id: str,
    req: BucketSearchRequest,
    svc: BucketService = Depends(_get_bucket_service),
    settings: Settings = Depends(get_settings),
):
    """Search within a bucket."""
    try:
        return svc.search(bucket_id, req.query, req.top_k, settings)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/buckets/{bucket_id}/chat")
@limiter.limit(LLM)
def chat_bucket(
    request: Request,
    bucket_id: str,
    req: BucketChatRequest,
    svc: BucketService = Depends(_get_bucket_service),
    settings: Settings = Depends(get_settings),
):
    """RAG chat scoped to a bucket."""
    try:
        return svc.chat(bucket_id, req.message, settings)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/buckets/{bucket_id}/add")
@limiter.limit(STANDARD)
def add_to_bucket(
    request: Request,
    bucket_id: str,
    req: AddToBucketRequest,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Add documents to an existing bucket. Files already present are skipped."""
    try:
        sources = [s.model_dump() for s in req.sources]
        return svc.add_documents(bucket_id, sources)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Bucket add failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Bucket add failed")


@router.post("/buckets/{bucket_id}/documents")
@limiter.limit(STANDARD)
def push_documents(
    request: Request,
    bucket_id: str,
    req: PushDocumentsRequest,
    svc: BucketService = Depends(_get_bucket_service),
):
    """Push markdown documents into a bucket by content — no filesystem access needed.

    Each document has a name (virtual filename) and content (raw markdown).
    Use this when the caller is on a different machine and can't provide
    a local directory path.
    """
    try:
        docs = [d.model_dump() for d in req.documents]
        return svc.push_documents(bucket_id, docs)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Bucket push failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Bucket push failed")
