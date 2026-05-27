"""File listing and management endpoints."""

import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import Settings
from app.deps import get_bucket_service, get_retriever, get_settings, get_store, get_tagdb, get_tracking
from app.events import IndexEvent, event_bus
from app.ingestion.indexer import ReindexError, reindex_file
from app.ingestion.scanner import _matches_ignore, discover_sources
from app.rag.retriever import Retriever
from app.ratelimit import HEAVY, STANDARD, limiter
from app.schemas.files import FileActionRequest, FileSearchRequest, SourceActionRequest, ToggleIndexRequest
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["files"])


@router.get("/file/status")
@limiter.limit(STANDARD)
def get_file_status(
    request: Request,
    path: str = Query(..., description="File path to check"),
    tracking: TrackingDB = Depends(get_tracking),
):
    """Get status of a single file (lightweight endpoint for file-viewer-dialog)."""
    # Virtual bucket documents live in ChromaDB, not the tracking DB.
    if path.startswith("bucket://"):
        return {
            "path": path,
            "status": "complete",
            "include_in_index": 1,
            "chunk_count": 0,
        }
    file = tracking.get_file(path)
    if not file:
        raise HTTPException(status_code=404, detail="File not found in tracking database")
    return {
        "path": file["path"],
        "status": file["status"],
        "include_in_index": file.get("include_in_index", 1),
        "chunk_count": file.get("chunk_count", 0),
    }


@router.get("/files")
@limiter.limit(STANDARD)
def list_files(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=100000),
    sort: str = Query("path", pattern="^(path|indexed_at)$"),
    settings: Settings = Depends(get_settings),
    tracking: TrackingDB = Depends(get_tracking),
    tagdb=Depends(get_tagdb),
    bucket_service=Depends(get_bucket_service),
):
    """List all discovered files, merging tracking DB info when available.

    Files assigned to a bucket are excluded — they appear in the Buckets tab.
    Each file includes a ``bucket_ids`` list (always empty here, kept for
    forward-compatibility if the filter is ever relaxed).

    Query parameters:
    - offset: pagination offset (default 0)
    - limit: results per page (default from settings.file_list_limit, max 100000)
    - sort: field to sort by — "path" (alphabetical) or "indexed_at" (most recent first)

    This is a read-only endpoint — pruning of stale records is handled by
    the indexer (run_index) and the explicit DELETE /api/v1/files/orphaned endpoint.
    """
    # Build lookup of tracked files
    tracked_map = {f["path"]: f for f in tracking.get_all_files()}

    # Build tag lookup from TagDB (if tags plugin is active)
    from app.domains.tag_registry import get_all_file_tags
    tag_map = {ft["path"]: ft["tags"] for ft in get_all_file_tags()}

    # Build bucket membership map (path → [bucket_ids]) — empty when plugin inactive
    bucketed_path_map: dict[str, list[str]] = (
        bucket_service.db.get_bucketed_path_map() if bucket_service else {}
    )

    # Discover all files across watch directories (lightweight, no hashing)
    discovered = discover_sources(settings.sources, settings.global_ignore, settings.source_file_filters)

    # Merge: tracked data wins, untracked files get synthetic entries
    merged = []
    discovered_paths: set[str] = set()
    for d in discovered:
        discovered_paths.add(d["path"])
        bucket_ids = bucketed_path_map.get(d["path"], [])
        if bucket_ids:
            # File belongs to a bucket — skip from Files tab
            tracked_map.pop(d["path"], None)
            continue
        tracked = tracked_map.pop(d["path"], None)
        if tracked:
            tracked = dict(tracked)
            tracked["tags"] = tag_map.get(d["path"], tracked.get("tags", ""))
            tracked["bucket_ids"] = []
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
                "include_in_index": 1,
                "tags": tag_map.get(d["path"], ""),
                "bucket_ids": [],
            })

    # Include tracked files not in discovery — mark missing ones
    for leftover in tracked_map.values():
        if bucketed_path_map.get(leftover["path"]):
            continue
        leftover = dict(leftover)
        leftover["tags"] = tag_map.get(leftover["path"], leftover.get("tags", ""))
        leftover["bucket_ids"] = []
        if not Path(leftover["path"]).exists():
            leftover["status"] = "missing"
        merged.append(leftover)

    # Sort by requested field
    if sort == "indexed_at":
        # Most recently indexed first (nulls last)
        merged.sort(key=lambda f: (f.get("indexed_at") is None, f.get("indexed_at")), reverse=True)
    else:
        # Default: alphabetical by path
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


@router.delete("/files/orphaned")
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
    path: str = Query(..., min_length=1, max_length=4096),
    page: int | None = Query(None, ge=1, description="Page number (1-based)"),
    page_size: int = Query(5000, ge=100, le=50000, description="Lines per page"),
    settings: Settings = Depends(get_settings),
    bucket_service=Depends(get_bucket_service),
):
    """Read file content, validating path is within configured sources.

    Supports optional pagination via ``page`` and ``page_size`` (in lines).
    When ``page`` is omitted the full content is returned.
    """
    # Virtual bucket documents (bucket://name/file.md) live in ChromaDB.
    # Reconstruct their content directly rather than touching the filesystem.
    if path.startswith("bucket://"):
        if bucket_service is None:
            raise HTTPException(status_code=503, detail="Bucket service unavailable")
        remainder = path[len("bucket://"):]
        bucket_name, _, _ = remainder.partition("/")
        record = bucket_service.db.resolve(bucket_name)
        if not record:
            raise HTTPException(status_code=404, detail=f"Bucket not found: {bucket_name}")
        store = bucket_service.get_store(record["id"])
        result = store._collection.get(
            where={"source_path": path},
            include=["documents", "metadatas"],
        )
        if not result["documents"]:
            raise HTTPException(status_code=404, detail="Document not found in bucket")
        chunks = sorted(
            zip(result["documents"], result["metadatas"]),
            key=lambda x: x[1].get("chunk_index", 0),
        )
        parts = []
        for doc, meta in chunks:
            lines = doc.split("\n", 2)
            if lines[0].startswith("From:") and len(lines) > 2:
                parts.append(lines[2])
            else:
                parts.append(doc)
        content = "\n\n".join(parts)
        return {
            "content": content,
            "page": 1,
            "total_pages": 1,
            "total_lines": len(content.splitlines()),
            "page_size": page_size,
        }

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
    # Paths that aren't under a configured source root may still be legitimate
    # bucket documents — buckets track their own source paths independently.
    # Allow reads of any path that a bucket knows about; the bucket plugin
    # already validated those paths when the bucket was created.
    if not allowed and bucket_service is not None:
        try:
            bucketed = bucket_service.db.get_bucketed_paths()
            if str(p) in bucketed or path in bucketed:
                allowed = True
        except Exception:
            logger.warning("Failed to check bucket paths for %s", path, exc_info=True)
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


@router.put("/files/include")
@limiter.limit(STANDARD)
def toggle_index(
    request: Request,
    req: ToggleIndexRequest,
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
    """Toggle whether a file is included in the index.

    Turning off deletes existing chunks and prevents future indexing.
    Turning on re-enables the file so the next scan will index it.
    """
    record = tracking.get_file(req.path)
    if not record:
        raise HTTPException(status_code=404, detail="File not tracked")
    if not req.include:
        store.delete_by_source(req.path)
        tracking.unindex_file(req.path)
    tracking.set_include_in_index(req.path, req.include)
    event_bus.publish(IndexEvent(
        type="index_toggled", path=req.path, filename=Path(req.path).name,
    ))
    return {"status": "ok", "include_in_index": req.include}


@router.get("/files/stale-ignored")
@limiter.limit(STANDARD)
def get_stale_ignored(
    request: Request,
    settings: Settings = Depends(get_settings),
    tracking: TrackingDB = Depends(get_tracking),
):
    """Return indexed files that now match the current global_ignore patterns.

    These files were indexed before a pattern was added and still have chunks
    in the vector store. Use DELETE /api/v1/files/stale-ignored to remove them.
    """
    patterns = settings.global_ignore
    if not patterns:
        return {"count": 0, "paths": []}
    all_files = tracking.get_all_files()
    stale = [
        f["path"] for f in all_files
        if f.get("chunk_count", 0) > 0 and _matches_ignore(f["path"], patterns)
    ]
    return {"count": len(stale), "paths": stale}


@router.delete("/files/stale-ignored")
@limiter.limit(STANDARD)
def purge_stale_ignored(
    request: Request,
    settings: Settings = Depends(get_settings),
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
    """Remove chunks and tracking records for files matching current global_ignore patterns.

    Safe to call at any time. Only affects files that have been indexed but now
    match an ignore pattern — does not touch unindexed or non-matching files.
    """
    patterns = settings.global_ignore
    if not patterns:
        return {"status": "ok", "purged": 0, "paths": []}
    all_files = tracking.get_all_files()
    stale = [f["path"] for f in all_files if _matches_ignore(f["path"], patterns)]
    for path in stale:
        store.delete_by_source(path)
        tracking.remove_file(path)
        logger.info("Purged stale-ignored file: %s", path)
    return {"status": "ok", "purged": len(stale), "paths": stale}


@router.delete("/files/index")
@limiter.limit(STANDARD)
def unindex_file(
    request: Request,
    req: FileActionRequest,
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
    """Remove a file's chunks from the vector store.

    With ``purge=false`` (default): resets status to pending and keeps the
    tracking row — the file can be re-indexed later from the same path.

    With ``purge=true``: deletes the tracking row entirely — the file will
    not appear in the Files tab or be re-indexed on next scan.  Use this
    when the file matches a global_ignore pattern or you want to forget it
    completely without deleting it from disk.
    """
    record = tracking.get_file(req.path)
    if not record:
        raise HTTPException(status_code=404, detail="File not tracked")
    chunks_removed = record["chunk_count"]
    store.delete_by_source(req.path)
    if req.purge:
        tracking.remove_file(req.path)
        return {"status": "purged", "chunks_removed": chunks_removed}
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
    tracking.set_include_in_index(req.path, True)
    try:
        result = reindex_file(req.path, settings, store, tracking)
    except ReindexError as e:
        logger.warning("Indexing failed for %s: %s", req.path, e)
        raise HTTPException(status_code=422, detail="Indexing failed for the requested file") from e
    return {"status": "ok", "message": result}


@router.put("/files/index")
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
        logger.warning("Reindexing failed for %s: %s", req.path, e)
        raise HTTPException(status_code=422, detail="Reindexing failed for the requested file") from e
    return {"status": "ok", "message": result}


@router.delete("/sources/index")
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
