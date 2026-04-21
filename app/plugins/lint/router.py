"""HTTP endpoints for lint."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_settings, get_retriever
from app.ratelimit import LLM, STANDARD, limiter
from app.plugins.lint.service import (
    PASS_ORDER, build_report, run_lint, write_report,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lint", tags=["lint"])


class RunLintRequest(BaseModel):
    passes: list[str] | None = Field(
        default=None,
        description="Subset of passes to run. Defaults to all four.",
    )
    target_wiki: str | None = Field(
        default=None,
        description="Wiki name to write the report into (falls back to "
        "{data_dir}/lint-reports). When set, the report appears inside "
        "that wiki's directory so it's itself indexable.",
    )


@router.post("/run")
@limiter.limit(LLM)
def run(
    request: Request,
    req: RunLintRequest,
    settings: Settings = Depends(get_settings),
    retriever=Depends(get_retriever),
):
    """Run the wiki lint. Returns findings + a markdown report.

    Also persists the report to disk so the file watcher picks it up
    and it joins the knowledge base as a retrievable document.
    """
    requested = req.passes or PASS_ORDER
    unknown = [p for p in requested if p not in PASS_ORDER]
    if unknown:
        raise HTTPException(400, f"Unknown lint pass(es): {unknown}")

    # Gather all managed wiki paths for pass 1's log.md scan.
    wiki_paths: list[Path] = []
    wikidb = getattr(request.app.state, "wikidb", None)
    if wikidb is not None:
        try:
            wiki_paths = [Path(w["path"]).resolve() for w in wikidb.list_all()]
        except Exception:
            logger.debug("Could not enumerate wikis for raw_coverage pass", exc_info=True)

    findings = run_lint(
        settings,
        wiki_paths=wiki_paths,
        retriever=retriever,
        passes=requested,
    )
    report_md = build_report(findings, passes_run=requested)

    target_dir: Path | None = None
    if req.target_wiki and wikidb is not None:
        record = wikidb.get_by_name(req.target_wiki)
        if not record:
            raise HTTPException(404, f"Wiki not found: {req.target_wiki}")
        target_dir = Path(record["path"])
    written_path = write_report(settings, report_md, target_dir=target_dir)

    # Summary counts by severity for UI badges.
    counts = {"critical": 0, "warning": 0, "info": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    return {
        "status": "ok",
        "findings": [f.to_dict() for f in findings],
        "counts": counts,
        "report_path": str(written_path),
        "report_markdown": report_md,
        "passes_run": requested,
    }


@router.get("/reports")
@limiter.limit(STANDARD)
def list_reports(
    request: Request,
    settings: Settings = Depends(get_settings),
):
    """List previously-generated lint reports sorted newest-first."""
    default_root = Path(settings.data_directory) / "lint-reports" / "lint"
    all_reports: list[dict] = []

    def _collect(base: Path):
        if not base.is_dir():
            return
        for p in sorted(base.glob("report-*.md"), reverse=True):
            try:
                stat = p.stat()
            except OSError:
                continue
            all_reports.append({
                "path": str(p),
                "name": p.name,
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime,
            })

    _collect(default_root)
    wikidb = getattr(request.app.state, "wikidb", None)
    if wikidb is not None:
        try:
            for w in wikidb.list_all():
                _collect(Path(w["path"]) / "lint")
        except Exception:
            logger.debug("Could not enumerate wiki dirs for reports", exc_info=True)

    all_reports.sort(key=lambda r: r["modified"], reverse=True)
    return {"reports": all_reports, "total": len(all_reports)}
