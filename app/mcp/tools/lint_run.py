"""MCP tool: run the tiered knowledge-base lint.

Mirrors the HTTP POST /api/lint/run endpoint.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import Settings

TOOL = {
    "name": "lint_run",
    "feature_flag": None,
    "requires_plugin": "lint",
    "write": False,   # produces a report file, but no doc mutation
}

_mcp = None  # Injected by register_tools()

logger = logging.getLogger(__name__)


def handler(
    passes: list[str] | None = None,
    target_wiki: str = "",
) -> dict:
    """Run the configured lint passes and return findings.

    Args:
        passes: Subset of passes to run. Defaults to all four
                (raw_coverage, orphan, within_tier, cross_tier).
        target_wiki: Wiki name to write the report into. When empty,
                     the report is stored under {data_dir}/lint-reports.
    """
    from app.plugins.lint.service import PASS_ORDER, build_report, run_lint, write_report

    ctx = _mcp.get_context()
    settings: Settings = ctx.request_context.lifespan_context["settings"]
    retriever = ctx.request_context.lifespan_context.get("retriever")
    wikidb = ctx.request_context.lifespan_context.get("wikidb")

    requested = passes or PASS_ORDER
    unknown = [p for p in requested if p not in PASS_ORDER]
    if unknown:
        raise ValueError(f"Unknown lint pass(es): {unknown}")

    wiki_paths: list[Path] = []
    if wikidb is not None:
        try:
            wiki_paths = [Path(w["path"]).resolve() for w in wikidb.list_all()]
        except Exception:
            logger.debug("Could not enumerate wikis", exc_info=True)

    findings = run_lint(
        settings, wiki_paths=wiki_paths, retriever=retriever, passes=requested,
    )
    report_md = build_report(findings, passes_run=requested)

    target_dir: Path | None = None
    if target_wiki and wikidb is not None:
        record = wikidb.get_by_name(target_wiki)
        if not record:
            raise ValueError(f"Wiki not found: {target_wiki}")
        target_dir = Path(record["path"])
    written = write_report(settings, report_md, target_dir=target_dir)

    counts = {"critical": 0, "warning": 0, "info": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    return {
        "findings_count": len(findings),
        "counts": counts,
        "report_path": str(written),
        "passes_run": requested,
        # Clip the inline markdown so agents don't get a huge blob back —
        # the full report lives at report_path and is now indexed.
        "report_preview": report_md[:4000],
    }
