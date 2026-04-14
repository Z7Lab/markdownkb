"""Orchestrator — runs selected passes and produces the lint report."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.plugins.lint.passes import (
    Finding, raw_coverage, orphans, within_tier, cross_tier,
)

logger = logging.getLogger(__name__)

PASS_ORDER = ["raw_coverage", "orphan", "within_tier", "cross_tier"]
SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


def run_lint(
    settings: Settings,
    *,
    wiki_paths: list[Path],
    retriever,
    passes: list[str] | None = None,
) -> list[Finding]:
    """Execute the requested passes. Unknown names are silently skipped."""
    requested = set(passes or PASS_ORDER)
    findings: list[Finding] = []

    if "raw_coverage" in requested:
        findings.extend(raw_coverage(settings, wiki_paths))
    if "orphan" in requested:
        findings.extend(orphans(settings))
    if "within_tier" in requested and retriever is not None:
        findings.extend(within_tier(settings, retriever))
    if "cross_tier" in requested and retriever is not None:
        findings.extend(cross_tier(settings, retriever))
    return findings


def build_report(findings: list[Finding], *, passes_run: list[str]) -> str:
    """Render findings as a single markdown document."""
    timestamp = datetime.now(timezone.utc).isoformat()
    lines: list[str] = [
        f"# Wiki lint report",
        "",
        f"- **Generated:** {timestamp}",
        f"- **Passes run:** {', '.join(passes_run) if passes_run else 'none'}",
        f"- **Findings:** {len(findings)}",
        "",
    ]
    if not findings:
        lines.append("No findings. The wiki is consistent under the rules this report applies.")
        return "\n".join(lines) + "\n"

    buckets: dict[str, list[Finding]] = {p: [] for p in PASS_ORDER}
    for f in findings:
        buckets.setdefault(f.pass_name, []).append(f)

    pass_titles = {
        "raw_coverage": "Raw coverage (tier-1: uncovered raw sources)",
        "orphan": "Orphans (tier-1 docs unlinked from anywhere)",
        "within_tier": "Within-tier contradictions (derived vs derived)",
        "cross_tier": "Cross-tier tensions (derived vs canonical)",
    }

    for pass_name in PASS_ORDER:
        entries = buckets.get(pass_name, [])
        if not entries:
            continue
        entries.sort(key=lambda f: SEVERITY_RANK.get(f.severity, 99))
        lines.append(f"## {pass_titles.get(pass_name, pass_name)}")
        lines.append("")
        for f in entries:
            lines.append(f"### {f.title}")
            lines.append("")
            lines.append(f"- **Severity:** {f.severity}")
            lines.append(f"- **Kind:** {f.kind}")
            if f.suggested_action:
                lines.append(f"- **Suggested:** {f.suggested_action}")
            lines.append("")
            lines.append(f.detail.strip())
            lines.append("")
            if f.paths:
                lines.append("**Paths:**")
                for p in f.paths[:40]:
                    lines.append(f"- `{p}`")
                if len(f.paths) > 40:
                    lines.append(f"- …and {len(f.paths) - 40} more")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(
    settings: Settings,
    report_md: str,
    *,
    target_dir: Path | None = None,
) -> Path:
    """Persist the report as markdown.

    Writes to ``{target_dir}/lint/report-<ISO>.md``. When target_dir is
    None, uses {data_dir}/lint-reports/ which is always writable.
    """
    if target_dir is None:
        target_dir = Path(settings.data_directory) / "lint-reports"
    dest_dir = target_dir / "lint"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = dest_dir / f"report-{stamp}.md"
    dest.write_text(report_md, encoding="utf-8")
    return dest
