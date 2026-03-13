"""Planner endpoints for MCTS plan generation, skill reviews, and saved plans."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_plandb, get_retriever, get_scopedb, get_settings, get_tracking
from app.rag.retriever import Retriever
from app.ratelimit import LLM, STANDARD, limiter
from app.schemas import PlanRequest
from app.scope_utils import parse_scope_ids, resolve_scopes
from app.tag_utils import resolve_tag_paths
from app.services.planner_service import list_skills, run_planner, stream_planner
from app.storage.plandb import PlanDB
from app.storage.scopedb import ScopeDB
from app.storage.trackingdb import TrackingDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/planner", tags=["planner"])


@router.post("/plan")
@limiter.limit(LLM)
def plan(
    request: Request,
    req: PlanRequest,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    scopedb: ScopeDB = Depends(get_scopedb),
    tracking: TrackingDB = Depends(get_tracking),
):
    """Generate an implementation plan using MCTS."""
    ids = parse_scope_ids(req.scope_ids) or ([req.scope_id] if req.scope_id else None)
    scope_folders, scope_tags = resolve_scopes(ids, scopedb)
    allowed = resolve_tag_paths(scope_tags, req.ad_hoc_tags)

    try:
        result = run_planner(
            req.request,
            retriever,
            settings,
            iterations=req.iterations,
            n_approaches=req.n_approaches,
            skill_names=req.skill_names,
            folders_filter=scope_folders,
            allowed_paths=allowed,
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
):
    """Stream plan generation progress as SSE events."""
    ids = parse_scope_ids(req.scope_ids) or ([req.scope_id] if req.scope_id else None)
    scope_folders, scope_tags = resolve_scopes(ids, scopedb)
    allowed = resolve_tag_paths(scope_tags, req.ad_hoc_tags)

    def generate():
        try:
            yield from stream_planner(
                req.request,
                retriever,
                settings,
                iterations=req.iterations,
                n_approaches=req.n_approaches,
                skill_names=req.skill_names,
                folders_filter=scope_folders,
                allowed_paths=allowed,
            )
        except RuntimeError as e:
            logger.error("Planner stream error: %s", e)
            from app.utils import sse
            yield sse("error", {"message": "Plan generation failed. Check server logs for details."})

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/plans")
@limiter.limit(STANDARD)
def list_plans(
    request: Request,
    plandb: PlanDB = Depends(get_plandb),
):
    """List saved plans, newest first."""
    return {"plans": plandb.list_plans()}


@router.post("/plans")
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
