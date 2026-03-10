"""File listing and management endpoints."""

import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import Settings
from app.deps import get_retriever, get_settings, get_store, get_tracking
from app.ingestion.indexer import ReindexError, reindex_file
from app.ingestion.scanner import discover_sources
from app.rag.retriever import Retriever
from app.ratelimit import STANDARD, limiter
from app.schemas import AutoTagApplyRequest, AutoTagPreviewRequest, BulkUpdateTagsRequest, FileActionRequest, FileSearchRequest, SourceActionRequest, ToggleRagRequest, UpdateTagsRequest
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
):
    """List all discovered files, merging tracking DB info when available.

    This is a read-only endpoint — pruning of stale records is handled by
    the indexer (run_index) and the explicit POST /api/files/prune endpoint.
    """
    # Build lookup of tracked files
    tracked_map = {f["path"]: f for f in tracking.get_all_files()}

    # Discover all files across watch directories (lightweight, no hashing)
    discovered = discover_sources(settings.sources, settings.global_ignore)

    # Merge: tracked data wins, untracked files get synthetic entries
    merged = []
    discovered_paths: set[str] = set()
    for d in discovered:
        discovered_paths.add(d["path"])
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
                "tags": "",
            })

    # Include tracked files not in discovery — mark missing ones
    for leftover in tracked_map.values():
        if not Path(leftover["path"]).exists():
            leftover = dict(leftover)
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
                except OSError:
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


@router.put("/files/tags")
@limiter.limit(STANDARD)
def update_file_tags(
    request: Request,
    req: UpdateTagsRequest,
    tracking: TrackingDB = Depends(get_tracking),
    settings: Settings = Depends(get_settings),
):
    """Update tags on a file — writes to both tracking DB and markdown frontmatter."""
    record = tracking.get_file(req.path)
    if not record:
        raise HTTPException(status_code=404, detail="File not tracked")

    tags_str = ", ".join(req.tags)
    tracking.update_tags(req.path, tags_str)

    return {"status": "ok", "tags": tags_str}


@router.put("/files/bulk-tags")
@limiter.limit(STANDARD)
def bulk_update_tags(
    request: Request,
    req: BulkUpdateTagsRequest,
    tracking: TrackingDB = Depends(get_tracking),
):
    """Update tags on multiple files at once.

    mode=add: merge new tags with existing
    mode=remove: remove specified tags from each file
    mode=replace: overwrite all tags on each file
    """
    updated = 0
    for path in req.paths:
        record = tracking.get_file(path)
        if not record:
            continue
        existing = {t.strip() for t in (record.get("tags") or "").split(",") if t.strip()}
        if req.mode == "add":
            merged = existing | set(req.tags)
        elif req.mode == "remove":
            merged = existing - set(req.tags)
        else:  # replace
            merged = set(req.tags)
        tracking.update_tags(path, ", ".join(sorted(merged)))
        updated += 1
    return {"status": "ok", "updated": updated}


@router.post("/files/auto-tag-preview")
@limiter.limit(STANDARD)
def auto_tag_preview(
    request: Request,
    req: AutoTagPreviewRequest,
    tracking: TrackingDB = Depends(get_tracking),
):
    """Dry-run auto-tagging: returns a plan mapping tags to file paths.

    strategy=subfolder: extract folder name at `depth` below base_path as tag.
    strategy=doc_type: extract the immediate parent folder name (e.g. implementation_docs).
    """
    base = req.base_path.rstrip("/")
    all_files = tracking.get_all_files()
    plan: dict[str, list[str]] = {}

    for f in all_files:
        path = f["path"]
        if not path.startswith(base + "/"):
            continue
        rest = path[len(base) + 1:]
        parts = rest.split("/")

        if req.strategy == "subfolder":
            if len(parts) <= req.depth:
                continue  # file is at or above the target depth
            tag = parts[req.depth - 1]
        else:  # doc_type
            if len(parts) < 2:
                continue
            tag = parts[-2]  # immediate parent folder

        if req.tag_prefix:
            tag = f"{req.tag_prefix}{tag}"
        plan.setdefault(tag, []).append(path)

    # Sort for stable output
    summary = []
    for tag in sorted(plan):
        summary.append({
            "tag": tag,
            "count": len(plan[tag]),
            "paths": sorted(plan[tag]),
        })

    return {
        "strategy": req.strategy,
        "base_path": base,
        "depth": req.depth,
        "tag_prefix": req.tag_prefix,
        "rules": summary,
        "total_files": sum(r["count"] for r in summary),
        "total_tags": len(summary),
    }


@router.post("/files/auto-tag-apply")
@limiter.limit(STANDARD)
def auto_tag_apply(
    request: Request,
    req: AutoTagApplyRequest,
    tracking: TrackingDB = Depends(get_tracking),
):
    """Apply an auto-tag plan (from preview). Adds tags without replacing existing ones."""
    total = 0
    for tag, paths in req.plan.items():
        for path in paths:
            record = tracking.get_file(path)
            if not record:
                continue
            existing = {t.strip() for t in (record.get("tags") or "").split(",") if t.strip()}
            if tag not in existing:
                merged = existing | {tag}
                tracking.update_tags(path, ", ".join(sorted(merged)))
                total += 1
    return {"status": "ok", "updated": total}


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


@router.get("/tags")
@limiter.limit(STANDARD)
def get_tags(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    retriever: Retriever = Depends(get_retriever),
    tracking: TrackingDB = Depends(get_tracking),
):
    """Get unique tags from indexed documents and tracking DB."""
    tags = set(retriever.get_unique_tags())
    for f in tracking.get_all_files():
        tag_str = f.get("tags", "")
        if tag_str:
            for t in tag_str.split(", "):
                if t.strip():
                    tags.add(t.strip())
    all_tags = sorted(tags)
    total = len(all_tags)
    items = all_tags[offset:offset + limit]
    return {"items": items, "total": total, "offset": offset, "limit": limit}
