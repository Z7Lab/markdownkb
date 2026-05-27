"""Tag management endpoints — CRUD, auto-tag, and optional AI generation."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_retriever, get_settings, get_tagdb, get_tracking
from app.plugins.tags.tagdb import TagDB
from app.rag.retriever import Retriever
from app.ratelimit import LLM, STANDARD, limiter
from app.storage.trackingdb import TrackingDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["tags"])


# -- Request schemas (plugin-local, not in core schemas.py) ------------------

class UpdateTagsRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=4096)
    tags: list[str]


class BulkUpdateTagsRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1)
    tags: list[str]
    mode: str = Field("add", pattern=r"^(add|remove|replace)$")


class AutoTagPreviewRequest(BaseModel):
    base_path: str = Field(..., description="Base directory to apply rules under")
    strategy: str = Field("subfolder", pattern=r"^(subfolder|doc_type)$")
    depth: int = Field(1, ge=1, le=5)
    tag_prefix: str = Field("", description="Optional prefix for generated tags")


class AutoTagApplyRequest(BaseModel):
    plan: dict = Field(..., description="Tag-to-paths mapping from preview")


class GenerateTagsRequest(BaseModel):
    file_path: str = Field(..., description="Path to markdown file")
    use_similar_docs: bool = Field(default=True)
    auto_apply: bool = Field(default=False)


class ApplyTagsRequest(BaseModel):
    file_path: str = Field(..., description="Path to markdown file")
    tags: list[str] = Field(..., description="Tags to apply")
    merge_with_existing: bool = Field(default=True)
    create_backup: bool = Field(default=True)


class BulkTagRequest(BaseModel):
    directory: str = Field(..., description="Directory to scan")
    pattern: str = Field(default="*.md")
    auto_apply: bool = Field(default=False)
    max_files: int = Field(default=50, ge=1, le=200)


# -- Helpers -----------------------------------------------------------------

def _require_tagdb(tagdb: TagDB | None) -> TagDB:
    if tagdb is None:
        raise HTTPException(status_code=503, detail="Tags plugin not initialized")
    return tagdb


def _check_ai_enabled(settings: Settings = Depends(get_settings)):
    """Guard for AI tag generation endpoints (sub-flag)."""
    if not settings.get_plugin_config("tags").get("ai_generation", False):
        raise HTTPException(
            status_code=403,
            detail="AI tag generation is disabled. Set plugins.tags.ai_generation: true in settings.",
        )


# -- Tag CRUD ----------------------------------------------------------------

@router.get("/tags")
@limiter.limit(STANDARD)
def get_tags(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    tagdb: TagDB | None = Depends(get_tagdb),
    retriever: Retriever = Depends(get_retriever),
):
    """Get unique tags from TagDB and indexed chunk metadata."""
    db = _require_tagdb(tagdb)
    tags = set(db.get_all_tags())
    # Also include tags from ChromaDB chunk metadata (frontmatter-sourced)
    tags.update(retriever.get_unique_tags())
    all_tags = sorted(tags)
    total = len(all_tags)
    items = all_tags[offset:offset + limit]
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.put("/files/tags")
@limiter.limit(STANDARD)
def update_file_tags(
    request: Request,
    req: UpdateTagsRequest,
    tagdb: TagDB | None = Depends(get_tagdb),
    tracking: TrackingDB = Depends(get_tracking),
):
    """Update tags on a file."""
    db = _require_tagdb(tagdb)
    # Verify the file is known (indexed or discovered)
    record = tracking.get_file(req.path)
    if not record:
        raise HTTPException(status_code=404, detail="File not tracked")
    tags_str = ", ".join(req.tags)
    db.update_tags(req.path, tags_str)
    return {"status": "ok", "tags": tags_str}


@router.put("/files/bulk-tags")
@limiter.limit(STANDARD)
def bulk_update_tags(
    request: Request,
    req: BulkUpdateTagsRequest,
    tagdb: TagDB | None = Depends(get_tagdb),
    tracking: TrackingDB = Depends(get_tracking),
):
    """Update tags on multiple files (add/remove/replace)."""
    db = _require_tagdb(tagdb)
    updated = 0
    for path in req.paths:
        record = tracking.get_file(path)
        if not record:
            continue
        existing = {t.strip() for t in db.get_tags(path).split(",") if t.strip()}
        if req.mode == "add":
            merged = existing | set(req.tags)
        elif req.mode == "remove":
            merged = existing - set(req.tags)
        else:  # replace
            merged = set(req.tags)
        db.update_tags(path, ", ".join(sorted(merged)))
        updated += 1
    return {"status": "ok", "updated": updated}


# -- Auto-tag (folder-structure based) --------------------------------------

@router.post("/files/auto-tag-preview")
@limiter.limit(STANDARD)
def auto_tag_preview(
    request: Request,
    req: AutoTagPreviewRequest,
    tracking: TrackingDB = Depends(get_tracking),
):
    """Dry-run auto-tagging: returns a plan mapping tags to file paths.

    strategy=subfolder: extract folder name at `depth` below base_path as tag.
    strategy=doc_type: extract the immediate parent folder name.
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
                continue
            tag = parts[req.depth - 1]
        else:  # doc_type
            if len(parts) < 2:
                continue
            tag = parts[-2]

        if req.tag_prefix:
            tag = f"{req.tag_prefix}{tag}"
        plan.setdefault(tag, []).append(path)

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
    tagdb: TagDB | None = Depends(get_tagdb),
):
    """Apply an auto-tag plan (from preview). Adds tags without replacing existing ones."""
    db = _require_tagdb(tagdb)
    total = 0
    for tag, paths in req.plan.items():
        for path in paths:
            existing = {t.strip() for t in db.get_tags(path).split(",") if t.strip()}
            if tag not in existing:
                merged = existing | {tag}
                db.update_tags(path, ", ".join(sorted(merged)))
                total += 1
    return {"status": "ok", "updated": total}


# -- AI tag generation (requires mcp_tag_generator sub-flag) -----------------

@router.post("/tags/generate")
@limiter.limit(LLM)
def generate_tags(
    request: Request,
    req: GenerateTagsRequest,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    tagdb: TagDB | None = Depends(get_tagdb),
    _: None = Depends(_check_ai_enabled),
):
    """Generate AI-powered tags for a markdown file."""
    from app.lib.tag_generator import auto_tag_file_interactive

    db = _require_tagdb(tagdb)
    try:
        result = auto_tag_file_interactive(
            req.file_path, retriever, settings, auto_apply=req.auto_apply,
        )
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        # Sync applied tags to TagDB
        if req.auto_apply and result.get("applied"):
            applied = result.get("final_tags", result.get("suggested_tags", []))
            if applied:
                db.update_tags(req.file_path, ", ".join(applied))
        return result
    except FileNotFoundError as e:
        logger.warning("Tag generation file missing: %s", e)
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error("Tag generation error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Tag generation failed.")


@router.post("/tags/apply")
@limiter.limit(STANDARD)
def apply_tags(
    request: Request,
    req: ApplyTagsRequest,
    tagdb: TagDB | None = Depends(get_tagdb),
    _settings: Settings = Depends(get_settings),
    __: None = Depends(_check_ai_enabled),
):
    """Apply specific tags to a markdown file's frontmatter and sync to TagDB."""
    from app.lib.tag_generator import apply_tags_to_file

    db = _require_tagdb(tagdb)
    try:
        result = apply_tags_to_file(
            req.file_path, req.tags,
            merge_with_existing=req.merge_with_existing,
            create_backup=req.create_backup,
        )
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        # Sync to TagDB
        final_tags = result.get("final_tags", req.tags)
        if final_tags:
            tags_str = ", ".join(final_tags) if isinstance(final_tags, list) else final_tags
            db.update_tags(req.file_path, tags_str)
        return result
    except FileNotFoundError as e:
        logger.warning("Tag apply file missing: %s", e)
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error("Tag application error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to apply tags.")


@router.post("/tags/bulk")
@limiter.limit(LLM)
def bulk_tag(
    request: Request,
    req: BulkTagRequest,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    tagdb: TagDB | None = Depends(get_tagdb),
    _: None = Depends(_check_ai_enabled),
):
    """Generate tags for multiple files in a directory using AI."""
    from app.lib.tag_generator import bulk_tag_directory

    db = _require_tagdb(tagdb)
    try:
        results = bulk_tag_directory(
            req.directory, retriever, settings,
            pattern=req.pattern, auto_apply=req.auto_apply, max_files=req.max_files,
        )
        # Sync applied tags to TagDB
        if req.auto_apply:
            for r in results:
                if r.get("applied") and r.get("final_tags"):
                    db.update_tags(r["file"], ", ".join(r["final_tags"]))
        return {"processed": len(results), "results": results}
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.error("Bulk tagging error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Bulk tagging failed.")
