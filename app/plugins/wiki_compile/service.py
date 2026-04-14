"""Wiki compilation service — the Ingest verb.

Reads a source document, asks an LLM to produce a summary page, writes it
to a writable source directory, and maintains two navigation files —
`index.md` (catalog, rewritten every ingest) and `log.md` (append-only
chronological record). Follows the three-layer / three-verb model from
Karpathy's LLM Wiki pattern.

Write-protection is enforced via `settings.is_source_writable`: the
target must be a configured source with `writable: true`. Canonical
(Tier-0) docs live under non-writable sources and are untouchable by
this plugin.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.rag.llm import get_completion, strip_thinking
from app.rag.retriever import Retriever
from app.plugins.wiki_compile.prompts import (
    EXISTING_CONTEXT_HEADER,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)

# Per-doc budget to keep prompt cost bounded. Larger than edge-explain
# (3000ch) because this is an explicit compilation pass, not an on-click
# explanation. 8000 ~= ~2000 tokens at typical markdown density.
MAX_SOURCE_CHARS = 8000

# Head of the source used as the embedding query. This is about
# query shape, not budget — most sources put their topic in the first
# ~1500 chars, and we don't want the whole 8000-char source as a query
# (signal dilutes, and we'd embed material that's in the source itself).
RETRIEVAL_QUERY_CHARS = 1500

_SAFE_SLUG_RE = re.compile(r"[^a-z0-9]+")


class WikiCompileError(Exception):
    """Raised for any caller-facing failure in the ingest path."""


def slugify(text: str) -> str:
    """Lowercase, strip to [a-z0-9-], collapse repeated separators."""
    s = _SAFE_SLUG_RE.sub("-", text.lower().strip())
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


def resolve_writable_target(target_source: str, settings: Settings) -> Path:
    """Return the resolved Path for ``target_source`` if it is a configured
    writable source. Raises WikiCompileError otherwise so the router can
    translate it into a 400 with a helpful list of valid targets.
    """
    if not target_source:
        raise WikiCompileError("target_source is required")
    requested = Path(target_source).expanduser().resolve()
    for cfg in settings.source_configs:
        if Path(cfg["path"]).resolve() == requested and cfg.get("writable"):
            return requested
    valid = settings.writable_sources
    raise WikiCompileError(
        f"target_source {requested} is not a configured writable source. "
        f"Valid targets: {valid}"
    )


def load_source_content(source_path: str) -> str:
    """Read a source file from disk, truncated to MAX_SOURCE_CHARS."""
    p = Path(source_path).expanduser()
    if not p.exists():
        raise WikiCompileError(f"source_path not found: {source_path}")
    if p.is_dir():
        raise WikiCompileError(f"source_path is a directory, not a file: {source_path}")
    text = p.read_text(encoding="utf-8", errors="replace")
    if len(text) > MAX_SOURCE_CHARS:
        text = text[:MAX_SOURCE_CHARS] + "\n\n[truncated]"
    return text


def fetch_existing_context(
    target_dir: Path,
    source_text: str,
    retriever: Retriever,
) -> str:
    """Retrieve related existing wiki pages from ``target_dir``.

    Uses the configured hybrid retriever scoped to the target directory
    (so we only see pages already in this wiki, not other indexed
    sources). The head of the new source is the embedding query — the
    first ~1500 chars usually captures the topic, and using the full
    8000-char source dilutes the signal and duplicates material that
    already appears below in the prompt.

    Context shape is driven entirely by the retriever's configuration —
    its ``top_k`` and score thresholds decide how much gets included.
    This function adds no additional token-budget caps so the behaviour
    scales correctly across deployment sizes: a small-context model
    with a low ``top_k`` naturally gets fewer pages; a large-context
    model with a higher ``top_k`` gets more. The retriever is the one
    knob.

    Returns a formatted markdown block ready to drop into the user
    prompt, or an empty string when the wiki is empty, retrieval is
    offline, or no related pages are found. Best-effort: never raises,
    never blocks ingest.
    """
    try:
        if retriever.store.count == 0:
            return ""
        query = source_text[:RETRIEVAL_QUERY_CHARS]
        results = retriever.search(
            query,
            folders_filter=[str(target_dir)],
        )
    except Exception as e:
        logger.warning("wiki_compile: existing-context retrieval failed: %s", e)
        return ""

    if not results:
        return ""

    skip_names = {str(target_dir / "index.md"), str(target_dir / "log.md")}
    seen: set[str] = set()
    unique_paths: list[str] = []
    for r in results:
        path = r.metadata.get("source_path", "")
        if not path or path in seen or path in skip_names:
            continue
        seen.add(path)
        unique_paths.append(path)

    if not unique_paths:
        return ""

    blocks = [EXISTING_CONTEXT_HEADER]
    for p in unique_paths:
        try:
            content = Path(p).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        blocks.append(f"\n### Existing: {Path(p).name}\n")
        blocks.append(content)
    return "\n".join(blocks)


def compile_summary(
    source_path: str,
    source_text: str,
    settings: Settings,
    existing_context: str = "",
) -> str:
    """Ask the configured LLM to produce the summary page.

    ``existing_context`` is an optional markdown block of related wiki
    pages already in the target. When non-empty, the LLM is instructed
    (via the system prompt) to note overlaps and contradictions in the
    new summary. Empty string preserves the v1 behavior exactly.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
            source_path=source_path,
            source_text=source_text,
            existing_context=existing_context,
        )},
    ]
    raw = get_completion(messages, settings)
    if not isinstance(raw, str):
        raise WikiCompileError("LLM returned a non-string completion (streaming mode?)")
    return strip_thinking(raw).strip()


def _first_heading(path: Path) -> str | None:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        return None
    return None


def _write_page(target_dir: Path, relative: str, content: str, overwrite: bool) -> Path:
    dest = target_dir / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        raise WikiCompileError(
            f"page already exists at {relative} — pass force=true to overwrite"
        )
    dest.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    return dest


def rebuild_index(target_dir: Path) -> Path:
    """Rewrite index.md from the current set of pages in target_dir.

    Enumerates every .md file under the target (excluding index.md and
    log.md themselves), groups by top-level subdirectory, and writes a
    sorted list of [title](rel-path) entries. Cheap to regenerate — runs
    every ingest.
    """
    groups: dict[str, list[tuple[str, str]]] = {}
    for md in sorted(target_dir.rglob("*.md")):
        rel = md.relative_to(target_dir)
        if rel.name in ("index.md", "log.md"):
            continue
        title = _first_heading(md) or rel.stem.replace("-", " ").title()
        group = rel.parts[0] if len(rel.parts) > 1 else "root"
        groups.setdefault(group, []).append((title, str(rel)))

    lines = ["# Wiki Index", ""]
    if not groups:
        lines.append("_no pages yet._")
    else:
        for group in sorted(groups):
            lines.append(f"## {group}")
            lines.append("")
            for title, path in sorted(groups[group]):
                lines.append(f"- [{title}]({path})")
            lines.append("")

    dest = target_dir / "index.md"
    dest.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return dest


def append_log(target_dir: Path, verb: str, detail: str) -> Path:
    """Append a chronological entry to log.md.

    Entry format (matches Karpathy's gist convention so 'grep ^## log.md'
    gives a parseable timeline):

        ## [YYYY-MM-DD] verb | detail
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = f"\n## [{ts}] {verb} | {detail}\n"
    dest = target_dir / "log.md"
    if dest.exists():
        existing = dest.read_text(encoding="utf-8")
        if not existing.endswith("\n"):
            existing += "\n"
    else:
        existing = "# Wiki Log\n\nChronological record of wiki changes.\n"
    dest.write_text(existing + entry, encoding="utf-8")
    return dest


def ingest(
    *,
    source_path: str,
    target_source: str,
    settings: Settings,
    retriever: Retriever | None = None,
    force: bool = False,
) -> dict:
    """Run a single ingest pass. Returns a dict the router serialises directly.

    When ``retriever`` is provided, the ingest fetches the most-related
    existing wiki pages from the target directory and passes them to the
    LLM as context, asking it to note overlaps/contradictions in the new
    summary. When ``retriever`` is None or retrieval yields nothing, the
    LLM call is identical to v1 — fully back-compatible.
    """
    target_dir = resolve_writable_target(target_source, settings)
    source_text = load_source_content(source_path)

    summary_rel = f"summaries/{slugify(Path(source_path).stem)}.md"
    summary_dest = target_dir / summary_rel
    if summary_dest.exists() and not force:
        raise WikiCompileError(
            f"summary page already exists at {summary_rel} — pass force=true to overwrite"
        )

    existing_context = ""
    existing_pages_used: list[str] = []
    if retriever is not None:
        existing_context = fetch_existing_context(target_dir, source_text, retriever)
        if existing_context:
            # Best-effort report of which pages got included, for the response.
            existing_pages_used = [
                line.split("Existing: ", 1)[1].strip()
                for line in existing_context.splitlines()
                if line.startswith("### Existing: ")
            ]

    summary_md = compile_summary(source_path, source_text, settings, existing_context)

    pages_written: list[str] = []
    pages_written.append(
        str(_write_page(target_dir, summary_rel, summary_md, overwrite=force).relative_to(target_dir))
    )
    pages_written.append(
        str(append_log(target_dir, "ingest", Path(source_path).name).relative_to(target_dir))
    )
    pages_written.append(
        str(rebuild_index(target_dir).relative_to(target_dir))
    )

    logger.info(
        "wiki_compile: ingested %s -> %s (%d chars summary, %d existing pages used)",
        source_path, target_dir, len(summary_md), len(existing_pages_used),
    )
    return {
        "status": "ok",
        "source_path": source_path,
        "target_source": str(target_dir),
        "pages_written": pages_written,
        "existing_pages_used": existing_pages_used,
        "summary_preview": summary_md[:300],
        "summary_chars": len(summary_md),
    }
