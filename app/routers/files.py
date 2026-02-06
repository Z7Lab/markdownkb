"""File listing and management endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import Settings
from app.deps import get_settings, get_store, get_tracking
from app.ingestion.indexer import reindex_file
from app.ratelimit import STANDARD, limiter
from app.schemas import FilePathRequest
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["files"])


@router.get("/files")
@limiter.limit(STANDARD)
def list_files(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
    # Prune files that no longer exist on disk
    all_files = tracking.get_all_files()
    existing_paths = {f["path"] for f in all_files if Path(f["path"]).exists()}
    removed = tracking.remove_files_not_in(existing_paths)
    for path in removed:
        store.delete_by_source(path)
        logger.info("Pruned missing file: %s", path)
    # Return paginated list
    total = tracking.file_count()
    items = tracking.get_all_files(offset=offset, limit=limit)
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/file")
@limiter.limit(STANDARD)
def read_file(
    request: Request,
    path: str,
    settings: Settings = Depends(get_settings),
):
    p = Path(path).resolve()
    # Validate the path is within a configured source directory
    allowed = False
    for source in settings.sources:
        source_resolved = Path(source).resolve()
        try:
            p.relative_to(source_resolved)
            allowed = True
            break
        except ValueError:
            continue
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Access denied: path is outside configured sources",
        )
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
        logger.error("Failed to read file %s: %s", p, e)
        raise HTTPException(
            status_code=500,
            detail="Failed to read file",
        ) from e


@router.post("/files/exclude")
@limiter.limit(STANDARD)
def exclude_file(
    request: Request,
    req: FilePathRequest,
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
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


@router.post("/files/include")
@limiter.limit(STANDARD)
def include_file(
    request: Request,
    req: FilePathRequest,
    settings: Settings = Depends(get_settings),
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
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
