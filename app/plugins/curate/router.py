"""HTTP surface for the curate plugin.

Endpoints:
- ``POST   /api/v1/curate/drafts``               — submit a bucket-C draft
- ``GET    /api/v1/curate/drafts``               — list drafts (the curation queue)
- ``POST   /api/v1/curate/drafts/{id}/graduate`` — gate 2: write into the corpus
- ``POST   /api/v1/curate/drafts/{id}/reject``   — discard a candidate
- ``DELETE /api/v1/curate/drafts/{id}``          — remove a draft record entirely
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_settings, get_versioning_manager
from app.plugins.curate.curatedb import CurateDB
from app.plugins.curate.service import (
    CurateError, graduate, reject, submit_draft, update_draft,
)
from app.ratelimit import STANDARD, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/curate", tags=["curate"])


# -- Request models ---------------------------------------------------------

class SubmitDraftRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    body_md: str = Field(..., min_length=1, description="Markdown body of the draft")
    taxonomy_slot: str = Field(
        ..., min_length=1,
        description="Corpus path the draft graduates into, e.g. 'patterns/error-handling'",
    )
    source_type: str = Field("", description="Origin kind: 'code' | 'bucket' | ...")
    source_ref: str = Field("", description="Origin reference: repo path, bucket id, ...")
    run_id: str | None = Field(None, description="Optional analysis-run correlation id")


class UpdateDraftRequest(BaseModel):
    title: str | None = Field(None, max_length=300)
    body_md: str | None = None
    taxonomy_slot: str | None = None


class GraduateRequest(BaseModel):
    target_source: str = Field(
        "", description="Writable source path to graduate into. Defaults to the first writable source.",
    )
    overwrite: bool = Field(False, description="Replace an existing document at the target path")


class RejectRequest(BaseModel):
    reason: str = Field("", max_length=2000)


# -- Helpers ----------------------------------------------------------------

def _get_curatedb(request: Request) -> CurateDB:
    curatedb = getattr(request.app.state, "curatedb", None)
    if curatedb is None:
        raise HTTPException(503, "CurateDB not initialized — plugin may be disabled")
    return curatedb


# -- Endpoints --------------------------------------------------------------

@router.post("/drafts")
@limiter.limit(STANDARD)
def create_draft(
    request: Request,
    req: SubmitDraftRequest,
    curatedb: CurateDB = Depends(_get_curatedb),
):
    """Gate 1 outcome: land a bucket-C candidate as a draft. Nothing touches
    the live corpus. Returns the draft plus any shape warnings."""
    try:
        return submit_draft(
            curatedb=curatedb,
            title=req.title,
            body_md=req.body_md,
            taxonomy_slot=req.taxonomy_slot,
            source_type=req.source_type,
            source_ref=req.source_ref,
            run_id=req.run_id,
        )
    except CurateError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/drafts")
@limiter.limit(STANDARD)
def list_drafts(
    request: Request,
    status: str | None = None,
    curatedb: CurateDB = Depends(_get_curatedb),
):
    """List drafts (the curation queue), optionally filtered by status."""
    drafts = curatedb.list_all(status=status)
    return {
        "drafts": drafts,
        "total": len(drafts),
        "counts": curatedb.counts_by_status(),
    }


@router.patch("/drafts/{draft_id}")
@limiter.limit(STANDARD)
def edit_draft(
    request: Request,
    draft_id: str,
    req: UpdateDraftRequest,
    curatedb: CurateDB = Depends(_get_curatedb),
):
    """Apply a curator's edits to an open draft (per-candidate edit gate)."""
    try:
        return update_draft(
            curatedb=curatedb,
            draft_id=draft_id,
            title=req.title,
            body_md=req.body_md,
            taxonomy_slot=req.taxonomy_slot,
        )
    except CurateError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/drafts/{draft_id}/graduate")
@limiter.limit(STANDARD)
def graduate_draft(
    request: Request,
    draft_id: str,
    req: GraduateRequest,
    settings: Settings = Depends(get_settings),
    curatedb: CurateDB = Depends(_get_curatedb),
    versioning_manager=Depends(get_versioning_manager),
):
    """Gate 2: a curator graduates a draft into the canonical corpus."""
    try:
        return graduate(
            curatedb=curatedb,
            settings=settings,
            draft_id=draft_id,
            target_source=req.target_source,
            overwrite=req.overwrite,
            versioning_manager=versioning_manager,
        )
    except CurateError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/drafts/{draft_id}/reject")
@limiter.limit(STANDARD)
def reject_draft(
    request: Request,
    draft_id: str,
    req: RejectRequest,
    curatedb: CurateDB = Depends(_get_curatedb),
):
    """Discard a candidate. The record is kept (status=rejected) for provenance."""
    try:
        return reject(curatedb=curatedb, draft_id=draft_id, reason=req.reason)
    except CurateError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/drafts/{draft_id}")
@limiter.limit(STANDARD)
def delete_draft(
    request: Request,
    draft_id: str,
    curatedb: CurateDB = Depends(_get_curatedb),
):
    """Permanently remove a draft record."""
    if not curatedb.delete(draft_id):
        raise HTTPException(404, f"draft not found: {draft_id}")
    return {"status": "deleted", "draft_id": draft_id}
