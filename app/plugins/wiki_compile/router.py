"""Wiki Compile plugin HTTP surface.

One write verb (POST /api/wiki-compile/ingest) and one read verb
(GET /api/wiki-compile/targets) for v1. See service.py for the logic.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_settings
from app.ratelimit import LLM, STANDARD, limiter
from app.plugins.wiki_compile.service import WikiCompileError, ingest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wiki-compile", tags=["wiki_compile"])


class IngestRequest(BaseModel):
    source_path: str = Field(..., min_length=1, description="Absolute path to a source file to ingest")
    target_source: str = Field(..., min_length=1, description="Configured writable source directory (must be writable: true)")
    force: bool = Field(False, description="Overwrite existing summary page if present")


@router.get("/targets")
@limiter.limit(STANDARD)
def list_targets(
    request: Request,
    settings: Settings = Depends(get_settings),
):
    """List writable sources that are valid ingest targets."""
    return {"targets": settings.writable_sources}


@router.post("/ingest")
@limiter.limit(LLM)
def ingest_endpoint(
    request: Request,
    req: IngestRequest,
    settings: Settings = Depends(get_settings),
):
    """Run one ingest pass (read source + LLM summary + index/log update)."""
    try:
        return ingest(
            source_path=req.source_path,
            target_source=req.target_source,
            settings=settings,
            force=req.force,
        )
    except WikiCompileError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        # get_completion raises RuntimeError when no LLM provider is usable
        logger.error("wiki_compile ingest LLM error: %s", e)
        raise HTTPException(status_code=503, detail="LLM request failed — check server logs")
