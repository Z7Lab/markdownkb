"""HTTP API for the versioning subsystem."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_settings
from app.ratelimit import STANDARD, limiter
from app.versioning.git_manager import GitManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/versioning", tags=["versioning"])


def _get_manager(request: Request) -> GitManager | None:
    return getattr(request.app.state, "versioning_manager", None)


def _resolve_versioned_source(
    file_path: str, settings: Settings
) -> tuple[Path, str]:
    """Return (source_dir, relative_path) for a versioned file.

    Raises HTTPException with a helpful message when the file isn't
    under a configured versioned source.
    """
    target = Path(file_path).expanduser().resolve()
    for cfg in settings.source_configs:
        source = Path(cfg["path"]).resolve()
        try:
            rel = target.relative_to(source)
        except ValueError:
            continue
        if not cfg.get("versioned"):
            raise HTTPException(
                404, f"{file_path} is under source {source} which is not versioned"
            )
        return source, str(rel)
    raise HTTPException(
        404,
        f"{file_path} is not under any configured source — nothing to version",
    )


class HistoryResponse(BaseModel):
    path: str
    source: str
    commits: list[dict]


@router.get("/history", response_model=HistoryResponse)
@limiter.limit(STANDARD)
def get_history(
    request: Request,
    path: str,
    limit: int = 50,
    settings: Settings = Depends(get_settings),
):
    """Return the commit history for a single file."""
    if not settings.versioning_enabled:
        raise HTTPException(503, "versioning is disabled")
    manager = _get_manager(request)
    if manager is None:
        raise HTTPException(503, "versioning manager not initialised")

    source, rel = _resolve_versioned_source(path, settings)
    commits = manager.log_for_file(source, rel, limit=limit)
    return HistoryResponse(
        path=path,
        source=str(source),
        commits=[
            {"sha": c.sha, "date": c.author_date, "subject": c.subject}
            for c in commits
        ],
    )


class DiffResponse(BaseModel):
    sha: str
    path: str
    diff: str


@router.get("/diff", response_model=DiffResponse)
@limiter.limit(STANDARD)
def get_diff(
    request: Request,
    path: str,
    commit: str,
    settings: Settings = Depends(get_settings),
):
    """Return the unified diff of ``path`` at ``commit`` vs its parent."""
    if not settings.versioning_enabled:
        raise HTTPException(503, "versioning is disabled")
    manager = _get_manager(request)
    if manager is None:
        raise HTTPException(503, "versioning manager not initialised")

    source, rel = _resolve_versioned_source(path, settings)
    diff = manager.diff_file(source, commit, rel)
    return DiffResponse(sha=commit, path=path, diff=diff)


class ContentResponse(BaseModel):
    sha: str
    path: str
    content: str | None


@router.get("/content", response_model=ContentResponse)
@limiter.limit(STANDARD)
def get_content_at(
    request: Request,
    path: str,
    commit: str,
    settings: Settings = Depends(get_settings),
):
    """Return the file's contents at a specific commit."""
    if not settings.versioning_enabled:
        raise HTTPException(503, "versioning is disabled")
    manager = _get_manager(request)
    if manager is None:
        raise HTTPException(503, "versioning manager not initialised")

    source, rel = _resolve_versioned_source(path, settings)
    content = manager.show_file_at(source, commit, rel)
    return ContentResponse(sha=commit, path=path, content=content)


class RestoreRequest(BaseModel):
    path: str = Field(..., description="Absolute path of the file to restore")
    commit: str = Field(..., description="Commit SHA to restore from")


class RestoreResponse(BaseModel):
    status: str
    restored_from: str
    new_commit: str | None


@router.post("/restore", response_model=RestoreResponse)
@limiter.limit(STANDARD)
def post_restore(
    request: Request,
    req: RestoreRequest,
    settings: Settings = Depends(get_settings),
):
    """Write a past revision back to disk as a new commit."""
    if not settings.versioning_enabled:
        raise HTTPException(503, "versioning is disabled")
    manager = _get_manager(request)
    if manager is None:
        raise HTTPException(503, "versioning manager not initialised")

    source, rel = _resolve_versioned_source(req.path, settings)
    try:
        new_sha = manager.restore_file(source, req.commit, rel)
    except Exception as exc:
        raise HTTPException(400, f"restore failed: {exc}")
    return RestoreResponse(
        status="restored",
        restored_from=req.commit,
        new_commit=new_sha,
    )
