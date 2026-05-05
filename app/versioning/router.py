"""HTTP API for the versioning subsystem."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_settings
from app.ratelimit import STANDARD, limiter
from app.versioning.git_manager import GitManager, GitManagerError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/versioning", tags=["versioning"])


def _get_manager(request: Request) -> GitManager | None:
    return getattr(request.app.state, "versioning_manager", None)


def _require_manager(request: Request, settings: Settings) -> GitManager:
    if not settings.versioning_enabled:
        raise HTTPException(503, "versioning is disabled")
    manager = _get_manager(request)
    if manager is None:
        raise HTTPException(503, "versioning manager not initialised")
    return manager


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


def _resolve_configured_source(path: str, settings: Settings) -> Path:
    """Return the resolved Path for an explicitly configured source.

    Raises 404 if the path is not one of the configured sources (versioned
    or not). Used by management endpoints that operate at source level.
    """
    resolved = Path(path).expanduser().resolve()
    for cfg in settings.source_configs:
        if Path(cfg["path"]).resolve() == resolved:
            return resolved
    raise HTTPException(404, f"{path} is not a configured source")


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
    manager = _require_manager(request, settings)
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


# -- Global status + per-source stats ----------------------------------------

@router.get("/status")
@limiter.limit(STANDARD)
def get_status(request: Request, settings: Settings = Depends(get_settings)):
    """Return the global versioning status plus per-source stats.

    Used by the Sources panel and the Versioning settings card.
    Always responds (no 503) so the UI can render a disabled state
    when versioning is off.
    """
    manager = _get_manager(request)
    sources = []
    total_commits = 0
    total_size = 0
    for cfg in settings.source_configs:
        path = str(Path(cfg["path"]).resolve())
        path_exists = Path(path).is_dir()
        entry = {
            "path": path,
            "writable": bool(cfg.get("writable")),
            "versioned": bool(cfg.get("versioned")),
            "path_accessible": path_exists,
        }
        if manager is not None and entry["versioned"]:
            stats = manager.repo_stats(path)
            entry.update(stats)
            total_commits += stats["commit_count"]
            total_size += stats["size_bytes"]
        else:
            entry.update({
                "initialised": False,
                "commit_count": 0,
                "last_commit_date": None,
                "size_bytes": 0,
            })
        sources.append(entry)
    return {
        "enabled": settings.versioning_enabled,
        "root": settings.versioning_root,
        "total_commits": total_commits,
        "total_size_bytes": total_size,
        "sources": sources,
    }


# -- Per-source actions ------------------------------------------------------

# Note: the global on/off toggle lives at PUT /api/v1/settings/core with
# name="versioning", so it sits alongside file_watcher, rag_chat, etc.
# No dedicated endpoint here.

class RepoPathRequest(BaseModel):
    path: str


@router.post("/init-repo")
@limiter.limit(STANDARD)
def post_init_repo(
    request: Request,
    req: RepoPathRequest,
    settings: Settings = Depends(get_settings),
):
    """Force-initialise the managed repo for a source.

    Useful when the initial startup init failed (permission issue, path
    not yet accessible, etc.) and the user has since fixed the cause.
    """
    manager = _require_manager(request, settings)
    source = _resolve_configured_source(req.path, settings)
    if not settings.is_source_versioned(str(source)):
        raise HTTPException(400, f"source {source} is not versioned — toggle versioning on first")
    try:
        manager.ensure_repo(source)
    except GitManagerError as exc:
        raise HTTPException(500, f"init failed: {exc}")
    return {"status": "ok", **manager.repo_stats(source)}


class PruneRequest(BaseModel):
    path: str
    keep_last_n: int | None = Field(None, ge=1)
    older_than_days: int | None = Field(None, ge=1)


@router.post("/prune")
@limiter.limit(STANDARD)
def post_prune(
    request: Request,
    req: PruneRequest,
    settings: Settings = Depends(get_settings),
):
    """Drop old commits and GC the repo. Destructive — no undo.

    Exactly one of ``keep_last_n`` or ``older_than_days`` must be set.
    """
    manager = _require_manager(request, settings)
    source = _resolve_configured_source(req.path, settings)
    try:
        result = manager.prune(
            source,
            keep_last_n=req.keep_last_n,
            older_than_days=req.older_than_days,
        )
    except GitManagerError as exc:
        raise HTTPException(400, str(exc))
    return {"status": "pruned", **result}


# -- Ignore file -------------------------------------------------------------

class IgnoreResponse(BaseModel):
    path: str
    contents: str


@router.get("/ignore", response_model=IgnoreResponse)
@limiter.limit(STANDARD)
def get_ignore(
    request: Request,
    path: str,
    settings: Settings = Depends(get_settings),
):
    """Return the per-source info/exclude contents."""
    manager = _require_manager(request, settings)
    source = _resolve_configured_source(path, settings)
    return IgnoreResponse(path=str(source), contents=manager.get_ignore(source))


class SetIgnoreRequest(BaseModel):
    path: str
    contents: str


@router.put("/ignore", response_model=IgnoreResponse)
@limiter.limit(STANDARD)
def put_ignore(
    request: Request,
    req: SetIgnoreRequest,
    settings: Settings = Depends(get_settings),
):
    """Overwrite the per-source info/exclude contents."""
    manager = _require_manager(request, settings)
    source = _resolve_configured_source(req.path, settings)
    manager.set_ignore(source, req.contents)
    return IgnoreResponse(path=str(source), contents=manager.get_ignore(source))


# -- Export ------------------------------------------------------------------

@router.get("/export")
@limiter.limit(STANDARD)
def get_export(
    request: Request,
    path: str,
    settings: Settings = Depends(get_settings),
):
    """Download the managed repo as a .tar.gz."""
    manager = _require_manager(request, settings)
    source = _resolve_configured_source(path, settings)
    if not manager.repo_exists(source):
        raise HTTPException(404, f"no managed repo for {source}")

    fd, tmp_path = tempfile.mkstemp(prefix="mdkb-versioning-", suffix=".tar.gz")
    import os
    os.close(fd)
    dest = Path(tmp_path)
    try:
        manager.export_tarball(source, dest)
    except GitManagerError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(500, f"export failed: {exc}")
    # Derive a friendly filename from the source basename.
    name = f"{source.name or 'source'}-versioning.tar.gz"
    return FileResponse(
        path=str(dest),
        media_type="application/gzip",
        filename=name,
        # Let starlette handle cleanup after the response is sent.
        background=None,
    )
