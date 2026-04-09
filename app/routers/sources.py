"""Source directory, project root, and ignore pattern endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import Settings
from app.deps import get_settings, get_store, get_tracking, get_watcher
from app.config.docker import in_docker, write_compose_override
from app.ratelimit import STANDARD, limiter
from app.schemas import (
    AddProjectRootRequest,
    AddSourceRequest,
    IgnorePatternRequest,
    RemoveProjectRootRequest,
    RemoveSourceRequest,
    UpdateProjectRootRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["sources"])


def _watch_and_index(watcher, path: str):
    """If the watcher is active, add a directory and index in background."""
    if watcher is None:
        return
    resolved = str(Path(path).resolve())
    if watcher.add_directory(resolved):
        import threading

        def _index_safe():
            try:
                watcher.index_directory(resolved)
            except Exception:
                logger.error("Background directory index failed for %s", resolved, exc_info=True)

        threading.Thread(target=_index_safe, daemon=True).start()


def _sync_compose_override(settings: Settings):
    """Regenerate compose.override.yml from current source configs."""
    try:
        project_root = settings._path.resolve().parent.parent
        write_compose_override(settings.source_configs, project_root)
    except Exception:
        logger.debug("Could not update compose.override.yml", exc_info=True)


# -- Sources --

@router.get("/sources")
@limiter.limit(STANDARD)
def get_sources(request: Request, settings: Settings = Depends(get_settings)):
    """Get list of source directories being watched."""
    sources = settings.sources
    inaccessible = [s for s in sources if not Path(s).is_dir()]
    result: dict = {"sources": sources}
    if inaccessible:
        result["inaccessible"] = inaccessible
        if in_docker():
            result["message"] = (
                "Some sources are not mounted into the container. "
                "Restart to apply: make down && make up"
            )
    return result


@router.post("/sources")
@limiter.limit(STANDARD)
def add_source(
    request: Request,
    req: AddSourceRequest,
    settings: Settings = Depends(get_settings),
    watcher=Depends(get_watcher),
):
    """Add a new source directory to watch.

    When the file watcher is running, the new directory is immediately
    watched and its files are indexed — no restart required.

    In Docker, newly added paths may not be mounted into the container.
    The response includes a ``docker_restart_required`` flag when the
    path is not accessible, with instructions to restart.
    """
    settings.add_source(req.path)
    settings.save()

    resolved = str(Path(req.path).resolve())
    accessible = Path(resolved).is_dir()

    if accessible:
        _watch_and_index(watcher, req.path)

    result: dict = {"sources": settings.sources}

    _sync_compose_override(settings)

    if not accessible and in_docker():
        result["docker_restart_required"] = True
        result["message"] = (
            f"Source added to config. '{req.path}' is not accessible inside the container yet. "
            "Restart to mount it: make down && make up"
        )

    return result


@router.delete("/sources")
@limiter.limit(STANDARD)
def remove_source(
    request: Request,
    req: RemoveSourceRequest,
    settings: Settings = Depends(get_settings),
    tracking=Depends(get_tracking),
    store=Depends(get_store),
):
    """Remove a source directory from watch list.

    When cleanup=true, also unindexes all files that were under this source.
    """
    resolved = str(Path(req.path).resolve())
    removed_count = 0

    if req.cleanup:
        all_files = tracking.get_all_files()
        for f in all_files:
            fpath = f["path"]
            if fpath.startswith(resolved + "/") or fpath.startswith(req.path + "/"):
                store.delete_by_source(fpath)
                tracking.unindex_file(fpath)
                removed_count += 1

    settings.remove_source(req.path)
    settings.save()
    _sync_compose_override(settings)
    return {"sources": settings.sources, "unindexed_count": removed_count}


# -- Ignore Patterns --

@router.post("/ignore-patterns")
@limiter.limit(STANDARD)
def add_ignore_pattern(
    request: Request,
    req: IgnorePatternRequest,
    settings: Settings = Depends(get_settings),
):
    """Add a glob pattern to the ignore list."""
    settings.add_ignore_pattern(req.pattern)
    settings.save()
    return {"global_ignore": settings.global_ignore}


@router.delete("/ignore-patterns")
@limiter.limit(STANDARD)
def remove_ignore_pattern(
    request: Request,
    req: IgnorePatternRequest,
    settings: Settings = Depends(get_settings),
):
    """Remove a glob pattern from the ignore list."""
    settings.remove_ignore_pattern(req.pattern)
    settings.save()
    return {"global_ignore": settings.global_ignore}


# -- Project Roots --

@router.get("/project-roots")
@limiter.limit(STANDARD)
def get_project_roots(request: Request, settings: Settings = Depends(get_settings)):
    """Get list of configured project roots."""
    return {"project_roots": settings.project_roots}


@router.post("/project-roots")
@limiter.limit(STANDARD)
def add_project_root(
    request: Request,
    req: AddProjectRootRequest,
    settings: Settings = Depends(get_settings),
    watcher=Depends(get_watcher),
):
    """Add a project root directory.

    The project root is scanned for subdirectories containing files that
    match the include patterns.  Each matching project is watched and
    indexed automatically.
    """
    settings.add_project_root(req.path, req.include, req.exclude)
    settings.save()
    for source in settings.sources:
        _watch_and_index(watcher, source)
    return {"project_roots": settings.project_roots}


@router.put("/project-roots")
@limiter.limit(STANDARD)
def update_project_root(
    request: Request,
    req: UpdateProjectRootRequest,
    settings: Settings = Depends(get_settings),
    watcher=Depends(get_watcher),
):
    """Update include/exclude patterns for a project root."""
    try:
        settings.update_project_root(req.path, req.include, req.exclude)
    except KeyError:
        raise HTTPException(404, f"Project root not found: {req.path}")
    settings.save()
    for source in settings.sources:
        _watch_and_index(watcher, source)
    return {"project_roots": settings.project_roots}


@router.delete("/project-roots")
@limiter.limit(STANDARD)
def remove_project_root(
    request: Request,
    req: RemoveProjectRootRequest,
    settings: Settings = Depends(get_settings),
    tracking=Depends(get_tracking),
    store=Depends(get_store),
):
    """Remove a project root.

    When cleanup=true, also unindexes all files from the expanded directories.
    """
    # Capture expanded dirs before removing so we can clean up
    removed_count = 0
    if req.cleanup:
        resolved_root = str(Path(req.path).resolve())
        all_files = tracking.get_all_files()
        for f in all_files:
            fpath = f["path"]
            if fpath.startswith(resolved_root + "/"):
                store.delete_by_source(fpath)
                tracking.unindex_file(fpath)
                removed_count += 1

    settings.remove_project_root(req.path)
    settings.save()
    return {"project_roots": settings.project_roots, "unindexed_count": removed_count}
