"""File listing and management endpoints."""

import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import Settings
from app.deps import get_retriever, get_settings, get_store, get_tagdb, get_tracking
from app.ingestion.indexer import ReindexError, reindex_file
from app.ingestion.scanner import discover_sources
from app.rag.retriever import Retriever
from app.ratelimit import HEAVY, STANDARD, limiter
from app.schemas import FileActionRequest, FileSearchRequest, SourceActionRequest, ToggleRagRequest
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
@limiter.limit(HEAVY)
def list_files(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=100000),
    settings: Settings = Depends(get_settings),
    tracking: TrackingDB = Depends(get_tracking),
    tagdb=Depends(get_tagdb),
):
    """List all discovered files, merging tracking DB info when available.

    This is a read-only endpoint — pruning of stale records is handled by
    the indexer (run_index) and the explicit POST /api/files/prune endpoint.
    """
    # Build lookup of tracked files
    tracked_map = {f["path"]: f for f in tracking.get_all_files()}

    # Build tag lookup from TagDB (if tags plugin is active)
    from app.tag_utils import get_all_file_tags
    tag_map = {ft["path"]: ft["tags"] for ft in get_all_file_tags()}

    # Discover all files across watch directories (lightweight, no hashing)
    discovered = discover_sources(settings.sources, settings.global_ignore)

    # Merge: tracked data wins, untracked files get synthetic entries
    merged = []
    discovered_paths: set[str] = set()
    for d in discovered:
        discovered_paths.add(d["path"])
        tracked = tracked_map.pop(d["path"], None)
        if tracked:
            tracked = dict(tracked)
            tracked["tags"] = tag_map.get(d["path"], tracked.get("tags", ""))
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
                "tags": tag_map.get(d["path"], ""),
            })

    # Include tracked files not in discovery — mark missing ones
    for leftover in tracked_map.values():
        leftover = dict(leftover)
        leftover["tags"] = tag_map.get(leftover["path"], leftover.get("tags", ""))
        if not Path(leftover["path"]).exists():
            leftover["status"] = "missing"
        merged.append(leftover)

    merged.sort(key=lambda f: f["path"])
    total = len(merged)
    effective_limit = limit if limit is not None else settings.file_list_limit
    items = merged[offset:offset + effective_limit]
    return {"items": items, "total": total, "offset": offset, "limit": effective_limit}


@router.post("/files/search")
@limiter.limit(STANDARD)
def search_files_by_content(
    request: Request,
    req: FileSearchRequest,
    retriever: Retriever = Depends(get_retriever),
):
    """Lightweight content search returning unique file paths.

    Used by the files tab content-search mode. No search history is saved.
    Supports quoted phrases: "exact phrase" requires literal match in file content.
    """
    # Extract quoted phrases and remaining terms
    exact_phrases = [m.lower() for m in re.findall(r'"([^"]+)"', req.query)]
    search_query = re.sub(r'"[^"]*"', '', req.query).strip() or req.query.strip('"')

    results = retriever.search(search_query, top_k=req.top_k * 5)
    seen: set[str] = set()
    paths: list[str] = []
    for r in results:
        src = r.metadata.get("source_path", "")
        if src and src not in seen:
            seen.add(src)
            # If exact phrases requested, verify they appear in the file
            if exact_phrases:
                try:
                    content = Path(src).read_text(encoding="utf-8", errors="replace").lower()
                    if not all(phrase in content for phrase in exact_phrases):
                        continue
                except OSError as e:
                    logger.warning("Skipping unreadable file in content search: %s: %s", src, e)
                    continue
            paths.append(src)
        if len(paths) >= req.top_k:
            break
    return {"paths": paths, "total": len(paths)}


@router.post("/files/prune")
@limiter.limit(STANDARD)
def prune_missing_files(
    request: Request,
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
    """Remove tracked files that no longer exist on disk.

    Deletes both tracking records and vector store chunks for missing files.
    This is safe to call at any time — the indexer also prunes at the start
    of each index run.
    """
    all_tracked = tracking.get_all_files()
    existing_paths = {f["path"] for f in all_tracked if Path(f["path"]).exists()}
    removed = tracking.remove_files_not_in(existing_paths)
    for path in removed:
        store.delete_by_source(path)
        logger.info("Pruned missing file: %s", path)
    return {"status": "ok", "pruned": len(removed), "paths": removed}


@router.get("/file")
@limiter.limit(STANDARD)
def read_file(
    request: Request,
    path: str,
    page: int | None = Query(None, ge=1, description="Page number (1-based)"),
    page_size: int = Query(5000, ge=100, le=50000, description="Lines per page"),
    settings: Settings = Depends(get_settings),
):
    """Read file content, validating path is within configured sources.

    Supports optional pagination via ``page`` and ``page_size`` (in lines).
    When ``page`` is omitted the full content is returned.
    """
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
        logger.warning("Access denied: %s is outside configured sources", p)
        raise HTTPException(
            status_code=403,
            detail="Access denied: path is outside configured sources",
        )
    if not p.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {path}",
        )
    try:
        content = p.read_text(
            encoding="utf-8",
            errors="replace",
        )
    except OSError as e:
        logger.error("Failed to read file %s: %s", p, e)
        raise HTTPException(
            status_code=500,
            detail="Failed to read file",
        ) from e

    if page is not None:
        lines = content.splitlines(keepends=True)
        total_lines = len(lines)
        total_pages = max(1, (total_lines + page_size - 1) // page_size)
        if page > total_pages:
            raise HTTPException(
                status_code=404,
                detail=f"Page {page} not found (file has {total_pages} page(s))",
            )
        start = (page - 1) * page_size
        end = start + page_size
        content = "".join(lines[start:end])
        return {
            "path": str(p),
            "content": content,
            "page": page,
            "total_pages": total_pages,
            "total_lines": total_lines,
            "page_size": page_size,
        }

    return {"path": str(p), "content": content}


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


@router.get("/folders")
@limiter.limit(STANDARD)
def get_folders(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    retriever: Retriever = Depends(get_retriever),
):
    """Get unique folder paths from indexed documents."""
    all_folders = retriever.get_unique_folders()
    total = len(all_folders)
    items = all_folders[offset:offset + limit]
    return {"items": items, "total": total, "offset": offset, "limit": limit}
