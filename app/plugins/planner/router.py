"""Planner endpoints for MCTS plan generation, skill reviews, and saved plans."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import (
    get_bucket_service,
    get_kgdb,
    get_plandb,
    get_retriever,
    get_scopedb,
    get_settings,
    get_tracking,
)
from app.rag.retriever import Retriever
from app.ratelimit import LLM, STANDARD, limiter
from app.plugins.planner.schemas import PlanRequest
from app.services.planner_service import list_skills, run_planner, stream_planner
from app.services.scope_service import resolve_request_scope
from app.storage.plandb import PlanDB
from app.storage.scopedb import ScopeDB
from app.storage.trackingdb import TrackingDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/planner", tags=["planner"])


@router.post("/plan")
@limiter.limit(LLM)
def plan(
    request: Request,
    req: PlanRequest,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    scopedb: ScopeDB = Depends(get_scopedb),
    tracking: TrackingDB = Depends(get_tracking),
    bucket_service=Depends(get_bucket_service),
    kgdb=Depends(get_kgdb),
):
    """Generate an implementation plan using MCTS."""
    bundle = resolve_request_scope(
        bucket_service=bucket_service,
        scope_ids=req.scope_ids,
        scope_id=req.scope_id,
        bucket_ids=req.bucket_ids,
        ad_hoc_tags=req.ad_hoc_tags,
        settings=settings,
        scopedb=scopedb,
    )
    scope_folders = bundle.scope_folders
    allowed = bundle.allowed_paths
    exclude_patterns = bundle.exclude_patterns
    bucket_retrievers = bundle.bucket_retrievers
    bucket_only = bundle.bucket_only

    # Planner uses a single secondary retriever; first bucket is primary in bucket_only mode
    first_bucket = bucket_retrievers[0] if bucket_retrievers else None
    try:
        result = run_planner(
            req.request,
            first_bucket if bucket_only else retriever,
            settings,
            iterations=req.iterations,
            n_approaches=req.n_approaches,
            skill_names=req.skill_names,
            folders_filter=scope_folders if not bucket_only else None,
            allowed_paths=allowed if not bucket_only else None,
            exclude_patterns=exclude_patterns if not bucket_only else None,
            bucket_retriever=first_bucket if not bucket_only else None,
            kgdb=kgdb,
        )
    except RuntimeError as e:
        logger.error("Planner error: %s", e)
        raise HTTPException(status_code=502, detail="Plan generation failed. Check server logs for details.")
    return result


@router.post("/plan/stream")
@limiter.limit(LLM)
def plan_stream(
    request: Request,
    req: PlanRequest,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    scopedb: ScopeDB = Depends(get_scopedb),
    tracking: TrackingDB = Depends(get_tracking),
    bucket_service=Depends(get_bucket_service),
    kgdb=Depends(get_kgdb),
):
    """Stream plan generation progress as SSE events."""
    bundle = resolve_request_scope(
        bucket_service=bucket_service,
        scope_ids=req.scope_ids,
        scope_id=req.scope_id,
        bucket_ids=req.bucket_ids,
        ad_hoc_tags=req.ad_hoc_tags,
        settings=settings,
        scopedb=scopedb,
    )
    scope_folders = bundle.scope_folders
    allowed = bundle.allowed_paths
    exclude_patterns = bundle.exclude_patterns
    bucket_retrievers_s = bundle.bucket_retrievers
    bucket_only = bundle.bucket_only
    first_bucket_s = bucket_retrievers_s[0] if bucket_retrievers_s else None

    def generate():
        try:
            yield from stream_planner(
                req.request,
                first_bucket_s if bucket_only else retriever,
                settings,
                iterations=req.iterations,
                n_approaches=req.n_approaches,
                skill_names=req.skill_names,
                folders_filter=scope_folders if not bucket_only else None,
                allowed_paths=allowed if not bucket_only else None,
                exclude_patterns=exclude_patterns if not bucket_only else None,
                bucket_retriever=first_bucket_s if not bucket_only else None,
                kgdb=kgdb,
            )
        except RuntimeError as e:
            logger.error("Planner stream error: %s", e)
            from app.transport import sse
            yield sse("error", {"message": "Plan generation failed. Check server logs for details."})

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/plans")
@limiter.limit(STANDARD)
def list_plans(
    request: Request,
    plandb: PlanDB = Depends(get_plandb),
):
    """List saved plans, newest first."""
    plans = plandb.list_plans()
    return {"plans": plans, "total": len(plans)}


@router.post("/plans", status_code=201)
@limiter.limit(STANDARD)
def save_plan(
    request: Request,
    req: dict,
    plandb: PlanDB = Depends(get_plandb),
):
    """Save a plan to the database."""
    title = req.get("title", "Untitled Plan")
    content = req.get("content", "")
    query = req.get("query", "")
    if not content:
        raise HTTPException(status_code=400, detail="Content is required")
    plan_id = plandb.save(title, content, query)
    return {"id": plan_id, "status": "saved"}


@router.get("/plans/{plan_id}")
@limiter.limit(STANDARD)
def get_plan(
    request: Request,
    plan_id: str,
    plandb: PlanDB = Depends(get_plandb),
):
    """Read a saved plan."""
    result = plandb.get(plan_id)
    if not result:
        raise HTTPException(status_code=404, detail="Plan not found")
    return result


@router.patch("/plans/{plan_id}")
@limiter.limit(STANDARD)
def rename_plan(
    request: Request,
    plan_id: str,
    req: dict,
    plandb: PlanDB = Depends(get_plandb),
):
    """Rename a saved plan."""
    title = req.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    if not plandb.rename(plan_id, title):
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"status": "renamed"}


@router.delete("/plans/{plan_id}")
@limiter.limit(STANDARD)
def delete_plan(
    request: Request,
    plan_id: str,
    plandb: PlanDB = Depends(get_plandb),
):
    """Delete a saved plan."""
    if not plandb.delete(plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"status": "deleted"}


@router.get("/skills")
@limiter.limit(STANDARD)
def get_skills(request: Request):
    """List available agent skills."""
    return {"skills": list_skills()}
