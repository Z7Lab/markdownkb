"""File listing and management endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import Settings
from app.deps import get_settings, get_store, get_tracking
from app.ingestion.indexer import ReindexError, reindex_file
from app.ingestion.scanner import discover_sources
from app.ratelimit import STANDARD, limiter
from app.schemas import FileActionRequest, SourceActionRequest, ToggleRagRequest
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["files"])


@router.get("/file/status")
@limiter.limit(STANDARD)
def get_file_status(
    request: Request,
    path: str = Query(..., description="File path to check"),
    tracking: TrackingDB = Depends(get_tracking),
):
    """Get status of a single file (lightweight endpoint for file-viewer-dialog)."""
    file = tracking.get_file(path)
    if not file:
        raise HTTPException(status_code=404, detail="File not found in tracking database")
    return {
        "path": file["path"],
        "status": file["status"],
        "include_rag": file.get("include_rag", 1),
        "chunk_count": file.get("chunk_count", 0),
    }


@router.get("/files")
@limiter.limit(STANDARD)
def list_files(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=100000),
    settings: Settings = Depends(get_settings),
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
    """List all discovered files, merging tracking DB info when available."""
    # Prune tracked files that no longer exist on disk
    all_tracked = tracking.get_all_files()
    existing_paths = {f["path"] for f in all_tracked if Path(f["path"]).exists()}
    removed = tracking.remove_files_not_in(existing_paths)
    for path in removed:
        store.delete_by_source(path)
        logger.info("Pruned missing file: %s", path)

    # Build lookup of tracked files
    tracked_map = {f["path"]: f for f in tracking.get_all_files()}

    # Discover all files across watch directories (lightweight, no hashing)
    discovered = discover_sources(settings.sources, settings.global_ignore)

    # Merge: tracked data wins, untracked files get synthetic entries
    merged = []
    for d in discovered:
        tracked = tracked_map.pop(d["path"], None)
        if tracked:
            merged.append(tracked)
        else:
            merged.append({
                "path": d["path"],
                "source_root": d["source_root"],
                "content_hash": "",
                "file_size": d["file_size"],
                "mtime": d["mtime"],
                "chunk_count": 0,
                "status": "not_indexed",
                "error_msg": None,
                "indexed_at": None,
                "updated_at": None,
                "include_rag": 1,
            })

    # Include any tracked files not in discovery
    for leftover in tracked_map.values():
        merged.append(leftover)

    merged.sort(key=lambda f: f["path"])
    total = len(merged)
    effective_limit = limit if limit is not None else settings.file_list_limit
    items = merged[offset:offset + effective_limit]
    return {"items": items, "total": total, "offset": offset, "limit": effective_limit}


@router.get("/file")
@limiter.limit(STANDARD)
def read_file(
    request: Request,
    path: str,
    settings: Settings = Depends(get_settings),
):
    """Read file content, validating path is within configured sources."""
    p = Path(path).resolve()
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


@router.put("/files/toggle-rag")
@limiter.limit(STANDARD)
def toggle_rag(
    request: Request,
    req: ToggleRagRequest,
    tracking: TrackingDB = Depends(get_tracking),
):
    """Toggle whether a file is included in RAG search results."""
    record = tracking.get_file(req.path)
    if not record:
        raise HTTPException(status_code=404, detail="File not tracked")
    tracking.set_include_rag(req.path, req.include)
    return {"status": "ok", "include_rag": req.include}


@router.post("/files/unindex")
@limiter.limit(STANDARD)
def unindex_file(
    request: Request,
    req: FileActionRequest,
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
    """Remove a file's chunks from the vector store and reset its status."""
    record = tracking.get_file(req.path)
    if not record:
        raise HTTPException(status_code=404, detail="File not tracked")
    chunks_removed = record["chunk_count"]
    store.delete_by_source(req.path)
    tracking.unindex_file(req.path)
    return {"status": "unindexed", "chunks_removed": chunks_removed}


@router.post("/files/index")
@limiter.limit(STANDARD)
def index_file(
    request: Request,
    req: FileActionRequest,
    settings: Settings = Depends(get_settings),
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
    """Index a single file that hasn't been indexed yet."""
    tracking.set_include_rag(req.path, True)
    try:
        result = reindex_file(req.path, settings, store, tracking)
    except ReindexError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"status": "ok", "message": result}


@router.post("/files/reindex")
@limiter.limit(STANDARD)
def reindex_single_file(
    request: Request,
    req: FileActionRequest,
    settings: Settings = Depends(get_settings),
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
    """Re-embed a single file's chunks."""
    record = tracking.get_file(req.path)
    if not record:
        raise HTTPException(status_code=404, detail="File not tracked")
    try:
        result = reindex_file(req.path, settings, store, tracking)
    except ReindexError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"status": "ok", "message": result}


@router.post("/files/unindex-source")
@limiter.limit(STANDARD)
def unindex_source(
    request: Request,
    req: SourceActionRequest,
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
    """Unindex all files under a given source directory."""
    source = str(Path(req.source).resolve())
    all_files = tracking.get_all_files()
    count = 0
    for f in all_files:
        if f["path"].startswith(source + "/") and f["status"] != "not_indexed":
            store.delete_by_source(f["path"])
            tracking.unindex_file(f["path"])
            count += 1
    return {"status": "ok", "unindexed": count}
