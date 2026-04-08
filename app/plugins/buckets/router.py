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
    sources: list[BucketSource] = Field(..., min_length=1)
    expires_in: int | None = Field(None, ge=60, description="Seconds until auto-delete")


class BucketSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(5, ge=1, le=50)


class BucketChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class AddToBucketRequest(BaseModel):
    sources: list[BucketSource] = Field(..., min_length=1)


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
    """List all buckets with metadata. Cleans up expired buckets first."""
    svc.cleanup_expired()
    buckets = svc.db.list_all()
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


@router.get("/buckets/{bucket_id}/files")
@limiter.limit(STANDARD)
def list_bucket_files(
    request: Request,
    bucket_id: str,
    svc: BucketService = Depends(_get_bucket_service),
):
    """List files in a bucket with chunk counts."""
    record = svc.db.resolve(bucket_id)
    if not record:
        raise HTTPException(status_code=404, detail="Bucket not found")
    store = svc._get_store(record["id"])
    all_meta = store.get_all_metadatas()
    # Group by source_path
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
    return {"files": file_list, "total": len(file_list)}


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
