"""Write API — create or update markdown documents via HTTP."""

import logging
import os
import re
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_settings, get_versioning_manager
from app.ratelimit import STANDARD, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

_write_lock = threading.Lock()

# Characters not allowed in filenames (beyond what the OS rejects)
_UNSAFE_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')


class CreateDocumentRequest(BaseModel):
    """Request to create or update a markdown document."""

    path: str = Field(
        ...,
        description="Relative path within the target source directory (e.g. 'notes/idea.md')",
    )
    content: str = Field(
        ...,
        description="Markdown content to write",
    )
    source: str = Field(
        "",
        description="Source directory to write into (must be a configured source). "
        "When empty, the first configured source is used.",
    )
    overwrite: bool = Field(
        False,
        description="Allow overwriting an existing file",
    )


def _validate_path(relative: str) -> str:
    """Sanitise and validate the relative path.

    Raises HTTPException on invalid input.
    """
    # Normalise and reject traversal
    normalized = Path(relative)
    if normalized.is_absolute():
        raise HTTPException(400, "Path must be relative")
    try:
        resolved = normalized.resolve()
        # resolve() on a relative path gives cwd-relative; we only care about
        # the parts, so just check for '..'
        for part in normalized.parts:
            if part == "..":
                raise HTTPException(400, "Path traversal ('..') is not allowed")
    except ValueError:
        raise HTTPException(400, "Invalid path")
    except OSError as e:
        logger.warning("Filesystem error validating path %r: %s", relative, e)
        raise HTTPException(500, "Filesystem error while validating path")

    if _UNSAFE_CHARS.search(relative):
        raise HTTPException(400, "Path contains invalid characters")

    if not relative.endswith(".md"):
        raise HTTPException(400, "Only .md files are supported")

    return str(normalized)


@router.post("")
@limiter.limit(STANDARD)
def create_document(
    request: Request,
    req: CreateDocumentRequest,
    settings: Settings = Depends(get_settings),
    manager=Depends(get_versioning_manager),
):
    """Create or update a markdown document in a watched source directory.

    The file is written to disk and picked up by the file watcher for
    automatic indexing.
    """
    relative = _validate_path(req.path)

    # Determine target source directory
    sources = settings.sources
    if not sources:
        raise HTTPException(400, "No source directories configured")

    if req.source:
        resolved_source = str(Path(req.source).resolve())
        resolved_sources = [str(Path(s).resolve()) for s in sources]
        if resolved_source not in resolved_sources:
            raise HTTPException(
                400,
                f"'{req.source}' is not a configured source directory. "
                f"Available: {resolved_sources}",
            )
        target_dir = Path(resolved_source)
    elif len(sources) == 1:
        target_dir = Path(sources[0])
    else:
        raise HTTPException(
            400,
            "Multiple source directories configured — 'source' field is required. "
            f"Available: {[str(Path(s).resolve()) for s in sources]}",
        )

    # Check writable flag
    if not settings.is_source_writable(str(target_dir)):
        raise HTTPException(
            403,
            f"Source '{target_dir}' is read-only (writable: false in settings)",
        )

    # Check path is accessible on disk
    if not target_dir.exists():
        raise HTTPException(
            422,
            f"Source directory does not exist or is not accessible: {target_dir}",
        )
    if not os.access(target_dir, os.W_OK):
        raise HTTPException(
            422,
            f"Source directory is not writable on disk: {target_dir}",
        )

    full_path = target_dir / relative

    with _write_lock:
        # Guard against overwriting without explicit flag
        if full_path.exists() and not req.overwrite:
            raise HTTPException(
                409,
                f"File already exists: {relative}. Set overwrite=true to replace.",
            )

        # Write the file
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(req.content, encoding="utf-8")
        except OSError as exc:
            logger.error("Failed to write document %s: %s", full_path, exc)
            raise HTTPException(500, "Failed to write file")

    logger.info("Document written: %s", full_path)

    # Best-effort version commit — never blocks the write.
    from app.versioning.hooks import try_commit
    verb = "update" if req.overwrite else "create"
    commit_sha = try_commit(
        settings, manager, target_dir,
        paths=[relative],
        message=f"write_api: {verb} {relative}",
    )

    return {
        "status": "created" if not req.overwrite else "written",
        "path": str(full_path),
        "relative_path": relative,
        "source": str(target_dir),
        "version_commit": commit_sha,
    }


@router.delete("")
@limiter.limit(STANDARD)
def delete_document(
    request: Request,
    path: str,
    source: str = "",
    settings: Settings = Depends(get_settings),
    manager=Depends(get_versioning_manager),
):
    """Delete a markdown document from a watched source directory."""
    relative = _validate_path(path)

    sources = settings.sources
    if not sources:
        raise HTTPException(400, "No source directories configured")

    if source:
        resolved_source = str(Path(source).resolve())
        resolved_sources = [str(Path(s).resolve()) for s in sources]
        if resolved_source not in resolved_sources:
            raise HTTPException(
                400,
                f"'{source}' is not a configured source directory. "
                f"Available: {resolved_sources}",
            )
        target_dir = Path(resolved_source)
    elif len(sources) == 1:
        target_dir = Path(sources[0])
    else:
        raise HTTPException(
            400,
            "Multiple source directories configured — 'source' parameter is required. "
            f"Available: {[str(Path(s).resolve()) for s in sources]}",
        )

    if not settings.is_source_writable(str(target_dir)):
        raise HTTPException(
            403,
            f"Source '{target_dir}' is read-only (writable: false in settings)",
        )

    full_path = target_dir / relative

    if not full_path.exists():
        raise HTTPException(404, f"File not found: {relative}")

    try:
        full_path.unlink()
    except OSError as exc:
        logger.error("Failed to delete document %s: %s", full_path, exc)
        raise HTTPException(500, "Failed to delete file")

    logger.info("Document deleted: %s", full_path)

    # Best-effort version commit — records the deletion.
    from app.versioning.hooks import try_commit
    commit_sha = try_commit(
        settings, manager, target_dir,
        paths=[relative],
        message=f"write_api: delete {relative}",
    )
    return {"status": "deleted", "path": str(full_path), "version_commit": commit_sha}
