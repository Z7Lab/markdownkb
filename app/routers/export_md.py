"""Export endpoints for markdown content and full snapshots.

GET /api/v1/export/markdown  — zip of all indexed .md files (sources + buckets + wikis)
GET /api/v1/export/snapshot  — full backup (DBs + vectors + config) + markdown in one tar.gz
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.backups.manager import BackupError, BackupManager, BackupOptions
from app.config import Settings
from app.deps import get_settings
from app.export.markdown_archive import MarkdownArchiveBuilder
from app.ratelimit import HEAVY, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/export", tags=["export"])


def _make_builder(request: Request, settings: Settings) -> MarkdownArchiveBuilder:
    bucket_svc = getattr(request.app.state, "bucket_service", None)
    return MarkdownArchiveBuilder(settings, bucket_service=bucket_svc)


# ── Markdown Archive ─────────────────────────────────────────────────────────


@router.get("/markdown")
@limiter.limit(HEAVY)
def export_markdown(request: Request, settings: Settings = Depends(get_settings)):
    """Download a zip of all indexed markdown files (sources, buckets, wikis)."""
    builder = _make_builder(request, settings)
    try:
        buf = builder.build_zip()
    except Exception as exc:
        logger.exception("Markdown archive build failed")
        raise HTTPException(500, f"export failed: {exc}") from exc
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    filename = f"mdkb-markdown-{ts}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Full Snapshot ─────────────────────────────────────────────────────────────


@router.get("/snapshot")
@limiter.limit(HEAVY)
def export_snapshot(request: Request, settings: Settings = Depends(get_settings)):
    """Download a full snapshot: databases, vectors, config, and all markdown files."""
    builder = _make_builder(request, settings)
    mgr = BackupManager(
        data_dir=Path(settings.data_directory),
        project_root=settings.project_root,
        app_version=getattr(request.app, "version", "0.0.0"),
    )
    fd, tmp = tempfile.mkstemp(prefix="mdkb-snapshot-", suffix=".tar.gz")
    os.close(fd)
    dest = Path(tmp)
    try:
        manifest = mgr.create(
            dest,
            BackupOptions(include_config=True, include_chromadb=True, include_sources=False),
            embedding_model=settings.embedding_model,
            staging_hook=builder.add_to_staging,
        )
    except (BackupError, Exception) as exc:
        dest.unlink(missing_ok=True)
        logger.exception("Snapshot build failed")
        raise HTTPException(500, f"snapshot failed: {exc}") from exc
    ts = manifest["created_at"].replace(":", "-")
    filename = f"mdkb-snapshot-{ts}.tar.gz"
    return FileResponse(
        path=str(dest),
        media_type="application/gzip",
        filename=filename,
    )
