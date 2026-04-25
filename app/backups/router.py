"""HTTP API for backup and restore."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.backups.manager import (
    BackupError,
    BackupManager,
    BackupOptions,
    RestoreError,
    RestoreOptions,
)
from app.config import Settings
from app.deps import get_settings
from app.ratelimit import HEAVY, STANDARD, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/backups", tags=["backups"])

# Read app version from FastAPI app instance (set in api.create_app).
def _manager(request: Request, settings: Settings) -> BackupManager:
    project_root = settings.project_root
    app_version = getattr(request.app, "version", "0.0.0")
    return BackupManager(
        data_dir=Path(settings.data_directory),
        project_root=project_root,
        app_version=app_version,
    )


# ── Status ──────────────────────────────────────────────────────────────

@router.get("/status")
@limiter.limit(STANDARD)
def get_status(request: Request, settings: Settings = Depends(get_settings)):
    """Report whether a restart is pending and rough data-dir size."""
    data_dir = Path(settings.data_directory)
    marker = data_dir / ".restart-required"
    pending = None
    if marker.is_file():
        try:
            import json
            pending = json.loads(marker.read_text())
        except Exception:
            pending = {"restored_at": "unknown"}
    size_bytes = _dir_size(data_dir)
    return {
        "data_dir": str(data_dir),
        "data_size_bytes": size_bytes,
        "restart_pending": pending,
        "mdkb_version": getattr(request.app, "version", "0.0.0"),
    }


@router.delete("/restart-marker")
@limiter.limit(STANDARD)
def clear_restart_marker(request: Request, settings: Settings = Depends(get_settings)):
    """Acknowledge a restored backup and clear the restart-required marker."""
    marker = Path(settings.data_directory) / ".restart-required"
    marker.unlink(missing_ok=True)
    return {"status": "cleared"}


# ── Create ──────────────────────────────────────────────────────────────

class CreateBackupQuery(BaseModel):
    include_config: bool = True
    include_sources: bool = False
    include_chromadb: bool = True
    include_markdown: bool = False


@router.post("/create")
@limiter.limit(HEAVY)
def create_backup(
    request: Request,
    body: CreateBackupQuery,
    settings: Settings = Depends(get_settings),
):
    """Build a backup archive and stream it back as a download."""
    import os
    from app.export.markdown_archive import MarkdownArchiveBuilder

    mgr = _manager(request, settings)
    fd, tmp = tempfile.mkstemp(prefix="mdkb-backup-", suffix=".tar.gz")
    os.close(fd)
    dest = Path(tmp)

    staging_hook = None
    if body.include_markdown:
        bucket_svc = getattr(request.app.state, "bucket_service", None)
        staging_hook = MarkdownArchiveBuilder(settings, bucket_service=bucket_svc).add_to_staging

    try:
        sources = [Path(s) for s in settings.sources] if body.include_sources else []
        manifest = mgr.create(
            dest,
            BackupOptions(
                include_config=body.include_config,
                include_sources=body.include_sources,
                include_chromadb=body.include_chromadb,
            ),
            sources=sources,
            embedding_model=settings.embedding_model,
            staging_hook=staging_hook,
        )
    except BackupError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(500, f"backup failed: {exc}") from exc
    except Exception as exc:
        dest.unlink(missing_ok=True)
        logger.exception("backup failed")
        raise HTTPException(500, f"backup failed: {exc}") from exc

    filename = f"mdkb-backup-{manifest['created_at'].replace(':', '-')}.tar.gz"
    return FileResponse(
        path=str(dest),
        media_type="application/gzip",
        filename=filename,
        headers={"X-Mdkb-Backup-Id": manifest["id"]},
    )


# ── Preview ─────────────────────────────────────────────────────────────

@router.post("/preview")
@limiter.limit(STANDARD)
async def preview_backup(
    request: Request,
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
):
    """Read the manifest from an uploaded archive without applying it."""
    fd, tmp = tempfile.mkstemp(prefix="mdkb-preview-", suffix=".tar.gz")
    import os
    os.close(fd)
    archive = Path(tmp)
    try:
        with archive.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        manifest = BackupManager.read_manifest(archive)
        return {"manifest": manifest}
    except RestoreError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        archive.unlink(missing_ok=True)


# ── Restore ─────────────────────────────────────────────────────────────

@router.post("/restore")
@limiter.limit(HEAVY)
async def restore_backup(
    request: Request,
    file: UploadFile = File(...),
    apply_config: bool = Form(True),
    apply_sources: bool = Form(False),
    settings: Settings = Depends(get_settings),
):
    """Apply an uploaded backup. Writes a restart-required marker on success."""
    fd, tmp = tempfile.mkstemp(prefix="mdkb-restore-", suffix=".tar.gz")
    import os
    os.close(fd)
    archive = Path(tmp)
    try:
        with archive.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        mgr = _manager(request, settings)
        manifest = mgr.restore(
            archive,
            RestoreOptions(apply_config=apply_config, apply_sources=apply_sources),
            current_embedding_model=settings.embedding_model,
        )
        return {
            "status": "restored",
            "restart_required": True,
            "manifest": manifest,
        }
    except RestoreError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("restore failed")
        raise HTTPException(500, f"restore failed: {exc}") from exc
    finally:
        archive.unlink(missing_ok=True)


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            continue
    return total
