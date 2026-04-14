"""MCP tool: file a generated answer back into the knowledge base.

This is the cloud-agent equivalent of the UI 'File as wiki page' button.
Design constraint from queue task ed5efc3a37ff: privacy boundary is
around the user's data, not the agent — cloud agents can invoke this
verb while the document still lands on the user's local filesystem.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings

TOOL = {
    "name": "promote_to_wiki",
    "feature_flag": "save_document",
    "write": True,
}

_mcp = None  # Injected by register_tools()

logger = logging.getLogger(__name__)

_UNSAFE_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(s: str) -> str:
    return _SLUG.sub("-", s.lower()).strip("-") or "note"


def _default_filename(content: str, suggested: str) -> str:
    heading_match = re.search(r"^\s*#+\s+(.+?)\s*$", content, re.MULTILINE)
    seed = heading_match.group(1) if heading_match else (suggested or content.splitlines()[0] if content else "note")
    return f"{_slug(seed)[:64] or 'note'}.md"


def _resolve_target(
    settings: Settings,
    target: str,
) -> Path:
    """Accept a wiki name or an absolute source path. Return the directory.

    Raises ValueError with a helpful message when the target can't be
    resolved or isn't writable.
    """
    # Try wiki name first — needs the WikiDB from the lifespan context.
    ctx = _mcp.get_context()
    wikidb = ctx.request_context.lifespan_context.get("wikidb")
    if wikidb is not None and target:
        record = wikidb.get_by_name(target)
        if record:
            return Path(record["path"]).resolve()

    # Fall back to treating it as a source path.
    if target:
        resolved = Path(target).expanduser().resolve()
    else:
        writable = settings.writable_sources
        if not writable:
            raise ValueError("No writable sources configured")
        resolved = Path(writable[0]).resolve()

    if str(resolved) not in [str(Path(s).resolve()) for s in settings.sources]:
        raise ValueError(
            f"'{target}' is not a configured source or wiki name. "
            f"Writable sources: {settings.writable_sources}"
        )
    if not settings.is_source_writable(str(resolved)):
        raise ValueError(f"Target '{resolved}' is read-only")
    if not resolved.is_dir():
        raise ValueError(f"Target directory does not exist: {resolved}")
    return resolved


def _build_document(
    content: str,
    *,
    kind: str,
    tags: list[str],
    sources: list[str],
    frontmatter: str,
) -> str:
    """Assemble the final markdown — frontmatter + body + compiled-from footer."""
    parts: list[str] = []
    now = datetime.now(timezone.utc)
    if frontmatter == "minimal":
        parts.append("---")
        parts.append(f"date: {now.strftime('%Y-%m-%d')}")
        parts.append(f"promoted_from: {kind}")
        if tags:
            parts.append(f"tags: [{', '.join(repr(t) for t in tags)}]")
        parts.extend(["---", ""])
    elif frontmatter == "full":
        parts.append("---")
        parts.append(f"date: {now.isoformat()}")
        parts.append(f"promoted_from: {kind}")
        if tags:
            parts.append(f"tags: [{', '.join(repr(t) for t in tags)}]")
        if sources:
            parts.append("compiled_from:")
            for s in sources:
                parts.append(f"  - {s!r}")
        parts.extend(["---", ""])
    parts.append(content.strip())
    if sources:
        parts.extend(["", "## Compiled from", ""])
        for s in sources:
            parts.append(f"- `{s}`")
    return "\n".join(parts) + "\n"


def handler(
    content: str,
    target: str = "",
    filename: str = "",
    kind: str = "custom",
    tags: list[str] | None = None,
    sources: list[str] | None = None,
    frontmatter: str = "minimal",
    overwrite: bool = False,
) -> dict:
    """File a generated answer back into a wiki or writable source.

    The counterpart to the UI 'File as wiki page' gesture. Closes the
    compounding loop so agent-produced answers become retrievable
    context for future queries.

    Args:
        content: Markdown body to file. Required.
        target: Wiki name (preferred) or absolute source path. When
                empty, uses the first writable source.
        filename: Relative .md filename inside the target. When empty,
                  derived from the first markdown heading or a slug of
                  the opening line.
        kind: Origin descriptor recorded in frontmatter — "chat",
              "search", "planner", or "custom".
        tags: Tag list stored in the frontmatter (minimal/full modes).
        sources: Absolute paths of documents the content was derived
                 from. Rendered as a 'Compiled from' footer so
                 provenance travels with the file.
        frontmatter: "none" / "minimal" / "full". Minimal adds date,
                     origin, and tags. Full adds ISO timestamp and the
                     compiled_from list.
        overwrite: Allow overwriting an existing file (default False).
    """
    if not content.strip():
        raise ValueError("content is required and must be non-empty")
    if frontmatter not in ("none", "minimal", "full"):
        raise ValueError("frontmatter must be 'none', 'minimal', or 'full'")
    if kind not in ("chat", "search", "planner", "custom"):
        raise ValueError("kind must be one of: chat, search, planner, custom")

    ctx = _mcp.get_context()
    settings: Settings = ctx.request_context.lifespan_context["settings"]

    target_dir = _resolve_target(settings, target)

    # Derive filename if not supplied.
    rel = filename.strip() or _default_filename(content, target)
    if Path(rel).is_absolute():
        raise ValueError("filename must be relative to the target")
    if ".." in Path(rel).parts:
        raise ValueError("filename may not contain '..'")
    if _UNSAFE_CHARS.search(rel):
        raise ValueError("filename contains invalid characters")
    if not rel.endswith(".md"):
        rel = f"{rel}.md"

    dest = target_dir / rel
    if dest.exists() and not overwrite:
        raise ValueError(
            f"File already exists: {rel}. Set overwrite=true to replace."
        )

    body = _build_document(
        content,
        kind=kind,
        tags=list(tags or []),
        sources=list(sources or []),
        frontmatter=frontmatter,
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")

    logger.info("Document promoted via MCP: %s (kind=%s)", dest, kind)

    # Best-effort version commit.
    version_commit = None
    try:
        from app.versioning.hooks import try_commit
        manager = ctx.request_context.lifespan_context.get("versioning_manager")
        version_commit = try_commit(
            settings, manager, target_dir,
            paths=[rel],
            message=f"mcp.promote_to_wiki: {kind} -> {rel}",
        )
    except Exception:
        logger.debug("MCP promote_to_wiki: versioning hook failed", exc_info=True)

    return {
        "status": "filed",
        "path": str(dest),
        "relative_path": rel,
        "target": str(target_dir),
        "bytes_written": len(body.encode("utf-8")),
        "version_commit": version_commit,
    }
