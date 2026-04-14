"""Lint passes — each returns a list of Finding dicts.

All passes are flag-only. Nothing here modifies documents; the caller
assembles a markdown report and the user decides what to act on.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from app.config import Settings
from app.rag.llm import get_completion, strip_thinking
from app.plugins.lint.prompts import (
    WITHIN_TIER_SYSTEM, WITHIN_TIER_USER,
    CROSS_TIER_SYSTEM, CROSS_TIER_USER,
)

logger = logging.getLogger(__name__)

# Keep each passage we send to the LLM bounded — full docs explode token budgets.
_MAX_DOC_CHARS = 6000
_MAX_PAIRS_PER_PASS = 12


@dataclass
class Finding:
    pass_name: str                    # "raw_coverage" | "orphan" | "within_tier" | "cross_tier"
    severity: str                     # "critical" | "warning" | "info"
    kind: str                         # pass-specific: "uncovered", "orphan", "contradiction", etc.
    title: str
    detail: str
    paths: list[str] = field(default_factory=list)
    suggested_action: str = ""

    def to_dict(self) -> dict:
        return {
            "pass": self.pass_name, "severity": self.severity, "kind": self.kind,
            "title": self.title, "detail": self.detail, "paths": self.paths,
            "suggested_action": self.suggested_action,
        }


# ---------------------------------------------------------------------------
# Pass 1 — RAW COVERAGE (deterministic)
# ---------------------------------------------------------------------------

def _iter_markdown(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return
    for p in root.rglob("*.md"):
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        yield p


def _wiki_log_sources(wiki_path: Path) -> set[str]:
    """Parse log.md and return the set of source filenames already ingested.

    Entries look like:  ## [2026-04-14] ingest | foo.md
    We extract whatever follows `ingest | ` to the end of line.
    """
    log = wiki_path / "log.md"
    if not log.is_file():
        return set()
    names: set[str] = set()
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return names
    for m in re.finditer(r"^##\s*\[[^\]]+\]\s*ingest\s*\|\s*(.+?)\s*$", text, re.MULTILINE):
        names.add(m.group(1).strip())
    return names


def raw_coverage(settings: Settings, wiki_paths: list[Path]) -> list[Finding]:
    """Flag raw (tier -1) documents that no wiki has synthesized yet."""
    raw_sources = settings.sources_by_tier(-1)
    if not raw_sources:
        return []

    synthesized: set[str] = set()
    for wp in wiki_paths:
        synthesized |= _wiki_log_sources(wp)

    findings: list[Finding] = []
    for src in raw_sources:
        root = Path(src["path"]).resolve()
        uncovered: list[str] = []
        for p in _iter_markdown(root):
            if p.name in synthesized:
                continue
            uncovered.append(str(p))
        if uncovered:
            findings.append(Finding(
                pass_name="raw_coverage",
                severity="warning" if len(uncovered) < 10 else "critical",
                kind="uncovered",
                title=f"{len(uncovered)} raw source(s) under {root} have no synthesis",
                detail=(
                    "These files appear under a tier=-1 (raw) source but no "
                    "managed wiki has an ingest log entry for them. Run the "
                    "wiki_compile ingest verb on the ones worth distilling."
                ),
                paths=uncovered,
                suggested_action="Ingest via wiki_compile, or mark truly-transient files to be excluded",
            ))
    return findings


# ---------------------------------------------------------------------------
# Pass 2 — ORPHANS (deterministic)
# ---------------------------------------------------------------------------

_MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)")


def _collect_links(path: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    refs: set[str] = set()
    for href in _MD_LINK_RE.findall(text):
        if href.startswith(("http://", "https://", "#", "mailto:")):
            continue
        refs.add(href.strip())
    return refs


def orphans(settings: Settings) -> list[Finding]:
    """Flag tier-1 docs no other doc links to.

    Link matching is suffix-based — we normalise both the target path
    (relative to any tier-1 source) and the link text's trailing
    segments, then compare. This handles same-wiki relative links and
    sibling-wiki cross-references without needing a full link resolver.
    """
    tier1 = settings.sources_by_tier(1)
    if not tier1:
        return []

    # Map: resolved doc path → {"name": basename, "relbits": last-N segments}
    docs: dict[Path, dict] = {}
    for src in tier1:
        root = Path(src["path"]).resolve()
        for p in _iter_markdown(root):
            rel = p.relative_to(root)
            docs[p] = {
                "name": p.name,
                "rel": str(rel),
                "tail": rel.as_posix(),
            }

    # Build set of referenced tails across all docs (tier-1 and tier-0 for completeness).
    all_sources = settings.source_configs
    referenced: set[str] = set()
    for src in all_sources:
        root = Path(src["path"]).resolve()
        for p in _iter_markdown(root):
            for href in _collect_links(p):
                # Normalise — strip anchor and leading ./ and leading slash.
                h = href.split("#", 1)[0].strip()
                h = h.lstrip("./").lstrip("/")
                if h:
                    referenced.add(h)
                    referenced.add(Path(h).name)

    # Auto-exclude navigation scaffolding — lint should not flag the wiki's
    # own index/log as orphans of itself.
    skip_names = {"index.md", "log.md", "README.md", "readme.md"}

    orphans: list[str] = []
    for p, meta in docs.items():
        if meta["name"] in skip_names:
            continue
        if meta["tail"] in referenced or meta["name"] in referenced:
            continue
        # Also check any trailing-segment match for deeper relative paths.
        parts = Path(meta["tail"]).parts
        hit = False
        for i in range(len(parts)):
            suffix = "/".join(parts[i:])
            if suffix in referenced:
                hit = True
                break
        if not hit:
            orphans.append(str(p))

    if not orphans:
        return []
    return [Finding(
        pass_name="orphan",
        severity="info",
        kind="orphan",
        title=f"{len(orphans)} derived doc(s) unreferenced by other docs",
        detail=(
            "These tier-1 documents aren't linked from any other document "
            "(same or different wiki). Retrieval may still surface them — "
            "this pass does not check retrieval frequency — but they "
            "aren't part of the explicit cross-reference graph. Consider "
            "linking them from an index, merging into a related page, "
            "or archiving."
        ),
        paths=orphans,
        suggested_action="Add a cross-reference link, merge with a related doc, or archive",
    )]


# ---------------------------------------------------------------------------
# Pass 3 — WITHIN-TIER contradictions (LLM)
# ---------------------------------------------------------------------------

def _read_doc(p: Path) -> str | None:
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if len(txt) > _MAX_DOC_CHARS:
        txt = txt[:_MAX_DOC_CHARS] + "\n\n[truncated]"
    return txt


def _select_doc_pairs(
    docs: list[Path], retriever, max_pairs: int,
) -> list[tuple[Path, Path]]:
    """Pick pairs of related docs using the retriever.

    For each doc, its top-k-nearest (by the configured retriever) is a
    candidate partner. Keeps the cost predictable regardless of corpus size.
    """
    pairs: list[tuple[Path, Path]] = []
    seen: set[frozenset[Path]] = set()
    for doc in docs:
        text = _read_doc(doc)
        if not text:
            continue
        try:
            results = retriever.search(text[:1500])
        except Exception:
            continue
        for r in results[:3]:
            path = r.metadata.get("source_path", "")
            if not path:
                continue
            partner = Path(path).resolve()
            if partner == doc:
                continue
            key = frozenset({doc, partner})
            if key in seen:
                continue
            seen.add(key)
            pairs.append((doc, partner))
            if len(pairs) >= max_pairs:
                return pairs
    return pairs


def within_tier(settings: Settings, retriever) -> list[Finding]:
    """LLM-flag contradictions among tier-1 docs (conservative prompt)."""
    tier1 = settings.sources_by_tier(1)
    if not tier1:
        return []

    docs: list[Path] = []
    for src in tier1:
        docs.extend(_iter_markdown(Path(src["path"]).resolve()))
    if len(docs) < 2:
        return []

    pairs = _select_doc_pairs(docs, retriever, _MAX_PAIRS_PER_PASS)
    findings: list[Finding] = []
    for a, b in pairs:
        a_text = _read_doc(a)
        b_text = _read_doc(b)
        if not a_text or not b_text:
            continue
        try:
            raw = get_completion(
                [
                    {"role": "system", "content": WITHIN_TIER_SYSTEM},
                    {"role": "user", "content": WITHIN_TIER_USER.format(
                        doc_a_path=str(a), doc_a=a_text,
                        doc_b_path=str(b), doc_b=b_text,
                    )},
                ],
                settings,
            )
        except Exception as exc:
            logger.warning("within_tier LLM call failed for %s/%s: %s", a.name, b.name, exc)
            continue
        body = strip_thinking(str(raw)).strip()
        verdict, explanation = _parse_verdict(body)
        if verdict != "contradicts":
            continue
        findings.append(Finding(
            pass_name="within_tier",
            severity="critical",
            kind="contradiction",
            title=f"Potential contradiction between {a.name} and {b.name}",
            detail=explanation,
            paths=[str(a), str(b)],
            suggested_action="Read both; merge, split with 'both sides' framing, or archive one",
        ))
    return findings


# ---------------------------------------------------------------------------
# Pass 4 — CROSS-TIER (LLM)
# ---------------------------------------------------------------------------

def cross_tier(settings: Settings, retriever) -> list[Finding]:
    """Classify tier-1 docs vs tier-0 canonical docs.

    For each tier-1 doc, find its top tier-0 neighbour (retriever) and
    ask the LLM: does this tier-1 doc EXTEND, CONTRADICT, or EVOLVE
    the canonical claim? Extension is informational; contradiction and
    evolution are surfaced for human review.
    """
    tier0 = settings.sources_by_tier(0)
    tier1 = settings.sources_by_tier(1)
    if not tier0 or not tier1:
        return []

    tier0_paths = {str(Path(p).resolve()) for src in tier0 for p in _iter_markdown(Path(src["path"]).resolve())}
    if not tier0_paths:
        return []

    tier1_docs: list[Path] = []
    for src in tier1:
        tier1_docs.extend(_iter_markdown(Path(src["path"]).resolve()))

    findings: list[Finding] = []
    count = 0
    for doc in tier1_docs:
        if count >= _MAX_PAIRS_PER_PASS:
            break
        text = _read_doc(doc)
        if not text:
            continue
        try:
            results = retriever.search(text[:1500])
        except Exception:
            continue
        canonical_match: Path | None = None
        for r in results[:10]:
            rpath = r.metadata.get("source_path", "")
            if rpath and rpath in tier0_paths:
                canonical_match = Path(rpath).resolve()
                break
        if canonical_match is None:
            continue
        canonical_text = _read_doc(canonical_match)
        if not canonical_text:
            continue
        try:
            raw = get_completion(
                [
                    {"role": "system", "content": CROSS_TIER_SYSTEM},
                    {"role": "user", "content": CROSS_TIER_USER.format(
                        tier1_path=str(doc), tier1_doc=text,
                        tier0_path=str(canonical_match), tier0_doc=canonical_text,
                    )},
                ],
                settings,
            )
        except Exception as exc:
            logger.warning("cross_tier LLM call failed for %s: %s", doc.name, exc)
            continue
        body = strip_thinking(str(raw)).strip()
        classification, explanation = _parse_verdict(body)
        if classification == "extension":
            severity = "info"
            suggested = "Consider promoting the extended dimension to canonical on a deliberate editing pass"
        elif classification == "contradiction":
            severity = "critical"
            suggested = "Reconcile manually: update canonical, archive derived, or document the tension"
        elif classification == "evolution":
            severity = "warning"
            suggested = "Candidate for Tier-0 promotion — review and update canonical on a deliberate pass"
        else:
            continue  # unknown/alignment-ok — nothing to report
        findings.append(Finding(
            pass_name="cross_tier",
            severity=severity,
            kind=classification,
            title=f"{classification.title()} — {doc.name} vs canonical {canonical_match.name}",
            detail=explanation,
            paths=[str(doc), str(canonical_match)],
            suggested_action=suggested,
        ))
        count += 1
    return findings


# ---------------------------------------------------------------------------
# Verdict parser — both within/cross prompts emit a fenced block with
# VERDICT: <label> and a free-form EXPLANATION.
# ---------------------------------------------------------------------------

def _parse_verdict(body: str) -> tuple[str, str]:
    verdict_match = re.search(r"VERDICT\s*:\s*(\w+)", body, re.IGNORECASE)
    verdict = (verdict_match.group(1).lower() if verdict_match else "").strip()
    # Everything after VERDICT line is the explanation.
    if verdict_match:
        explanation = body[verdict_match.end():].strip()
        # Strip a leading "EXPLANATION:" if the model emitted one.
        explanation = re.sub(r"^EXPLANATION\s*:\s*", "", explanation, flags=re.IGNORECASE).strip()
    else:
        explanation = body
    return verdict, explanation
