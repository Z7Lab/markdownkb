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
from app.plugins.wiki_compile.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

# Per-doc budget to keep prompt cost bounded. Larger than edge-explain
# (3000ch) because this is an explicit compilation pass, not an on-click
# explanation. 8000 ~= ~2000 tokens at typical markdown density.
MAX_SOURCE_CHARS = 8000

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


def compile_summary(source_path: str, source_text: str, settings: Settings) -> str:
    """Ask the configured LLM to produce the summary page."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
            source_path=source_path, source_text=source_text,
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
    force: bool = False,
) -> dict:
    """Run a single ingest pass. Returns a dict the router serialises directly."""
    target_dir = resolve_writable_target(target_source, settings)
    source_text = load_source_content(source_path)

    summary_rel = f"summaries/{slugify(Path(source_path).stem)}.md"
    summary_dest = target_dir / summary_rel
    if summary_dest.exists() and not force:
        raise WikiCompileError(
            f"summary page already exists at {summary_rel} — pass force=true to overwrite"
        )

    summary_md = compile_summary(source_path, source_text, settings)

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
        "wiki_compile: ingested %s -> %s (%d chars summary)",
        source_path, target_dir, len(summary_md),
    )
    return {
        "status": "ok",
        "source_path": source_path,
        "target_source": str(target_dir),
        "pages_written": pages_written,
        "summary_preview": summary_md[:300],
        "summary_chars": len(summary_md),
    }
