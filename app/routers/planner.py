"""Planner endpoints for MCTS plan generation and skill reviews."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_retriever, get_settings
from app.rag.retriever import Retriever
from app.ratelimit import LLM, STANDARD, limiter
from app.schemas import PlanRequest
from app.services.planner_service import list_skills, run_planner, stream_planner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/planner", tags=["planner"])


@router.post("/plan")
@limiter.limit(LLM)
def plan(
    request: Request,
    req: PlanRequest,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
):
    """Generate an implementation plan using MCTS."""
    try:
        result = run_planner(
            req.request,
            retriever,
            settings,
            iterations=req.iterations,
            n_approaches=req.n_approaches,
            skill_names=req.skill_names,
        )
    except RuntimeError as e:
        logger.error("Planner error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    return result


@router.post("/plan/stream")
@limiter.limit(LLM)
def plan_stream(
    request: Request,
    req: PlanRequest,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
):
    """Stream plan generation progress as SSE events."""
    def generate():
        try:
            yield from stream_planner(
                req.request,
                retriever,
                settings,
                iterations=req.iterations,
                n_approaches=req.n_approaches,
                skill_names=req.skill_names,
            )
        except RuntimeError as e:
            logger.error("Planner stream error: %s", e)
            from app.utils import sse
            yield sse("error", {"message": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/skills")
@limiter.limit(STANDARD)
def get_skills(request: Request):
    """List available agent skills."""
    return {"skills": list_skills()}
