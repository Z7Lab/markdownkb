"""Curate service — the analyze–match–codify graduation path.

Three verbs over the draft store:

- ``submit_draft`` — land a bucket-C candidate as ``status=draft``. Nothing
  touches the live corpus. Validates the candidate carries the guide's
  required shape (general pattern, rationale, worked example, taxonomy
  slot, honest TODOs) and surfaces shape warnings rather than silently
  accepting a thin stub.
- ``graduate`` — the **gated analog of ``promote_to_wiki``**. Same write
  primitive (resolve a writable source, build a document, write, log,
  version-commit) with the draft store + two human gates in front. Writes
  into the canonical knowledge_docs tree at the path implied by the
  draft's ``taxonomy_slot``, with provenance in frontmatter.
- ``reject`` — mark a candidate ``rejected`` with a reason; kept for
  provenance, never written to the corpus.

Graduation honors the same three write controls as the rest of mdkb: the
target must be a configured ``writable: true`` source, and (on the MCP
path) ``mcp.save_document`` must be on. When no writable source exists,
graduation surfaces a clear "unavailable" error rather than a silent
no-op. It also refuses paths matching ``settings.global_ignore`` — a file
written under an ignored segment is written but never indexed, silently
breaking the compounding loop.
"""

from __future__ import annotations

import fnmatch
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.plugins.curate.curatedb import CurateDB

logger = logging.getLogger(__name__)

_SAFE_SLUG_RE = re.compile(r"[^a-z0-9]+")
_curate_log_lock = threading.Lock()

# Sections a well-formed bucket-C draft carries (per the corpus-growth
# guide). Missing ones produce warnings, not hard failures — the agent
# path stays usable, but a thin stub doesn't slip through unnoticed.
_RECOMMENDED_SECTIONS = {
    "rationale": ("why it works", "why-it-works", "what it prevents", "rationale"),
    "worked example": ("example", "worked example"),
    "honest TODOs": ("todo", "todos", "to do", "open question", "gap"),
}


class CurateError(Exception):
    """Raised for any caller-facing failure in the curate path."""


def slugify(text: str) -> str:
    """Lowercase, strip to [a-z0-9-], collapse repeated separators."""
    s = _SAFE_SLUG_RE.sub("-", text.lower().strip())
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


# -- submit ------------------------------------------------------------------

def validate_draft_shape(title: str, body_md: str, taxonomy_slot: str) -> list[str]:
    """Check a candidate carries the guide's required shape.

    Hard requirements (raise ``CurateError``): a title, a non-trivial body,
    and a taxonomy slot (it determines the graduation path). Everything else
    — rationale, a worked example, honest TODOs — is returned as a list of
    soft warnings so the curator sees what's thin before graduating.
    """
    if not title.strip():
        raise CurateError("title is required")
    if len(body_md.strip()) < 80:
        raise CurateError(
            "body_md is too thin to be a draft — include the general pattern, "
            "why it works, a worked example, and honest TODOs"
        )
    if not taxonomy_slot.strip():
        raise CurateError(
            "taxonomy_slot is required — it determines where the draft graduates "
            "into the corpus (e.g. 'patterns/error-handling')"
        )

    lowered = body_md.lower()
    warnings: list[str] = []
    for label, needles in _RECOMMENDED_SECTIONS.items():
        if not any(n in lowered for n in needles):
            warnings.append(f"draft appears to be missing a {label} section")
    return warnings


def submit_draft(
    *,
    curatedb: CurateDB,
    title: str,
    body_md: str,
    taxonomy_slot: str,
    source_type: str = "",
    source_ref: str = "",
    run_id: str | None = None,
) -> dict:
    """Validate and persist a bucket-C candidate as ``status=draft``.

    Returns a dict the router/MCP tool serialises directly, including any
    ``shape_warnings`` so a thin stub is flagged at submit time.
    """
    warnings = validate_draft_shape(title, body_md, taxonomy_slot)
    record = curatedb.create(
        title=title.strip(),
        body_md=body_md.strip(),
        taxonomy_slot=taxonomy_slot.strip().strip("/"),
        source_type=source_type.strip(),
        source_ref=source_ref.strip(),
        run_id=run_id,
    )
    logger.info(
        "curate: drafted %s (taxonomy=%s, source=%s/%s, %d shape warnings)",
        record["id"], record["taxonomy_slot"], source_type, source_ref, len(warnings),
    )
    return {"draft": record, "shape_warnings": warnings}


# -- edit --------------------------------------------------------------------

def update_draft(
    *,
    curatedb: CurateDB,
    draft_id: str,
    title: str | None = None,
    body_md: str | None = None,
    taxonomy_slot: str | None = None,
) -> dict:
    """Apply a curator's edits to an open draft (the per-candidate edit gate).

    Only ``draft``-status rows are editable; graduated/rejected rows are
    immutable. Re-validates the resulting shape and returns the updated
    draft plus any ``shape_warnings``.
    """
    draft = curatedb.get(draft_id)
    if not draft:
        raise CurateError(f"draft not found: {draft_id}")
    if draft["status"] != "draft":
        raise CurateError(
            f"draft {draft_id} is {draft['status']} — only open drafts are editable"
        )

    new_title = (title if title is not None else draft["title"]).strip()
    new_body = (body_md if body_md is not None else draft["body_md"]).strip()
    new_slot = (taxonomy_slot if taxonomy_slot is not None else draft["taxonomy_slot"]).strip().strip("/")

    warnings = validate_draft_shape(new_title, new_body, new_slot)
    curatedb.update(draft_id, title=new_title, body_md=new_body, taxonomy_slot=new_slot)
    return {"draft": curatedb.get(draft_id), "shape_warnings": warnings}


# -- graduate ----------------------------------------------------------------

def _resolve_writable_target(settings: Settings, target: str) -> Path:
    """Return the resolved directory for ``target`` if it is a configured
    writable source. When ``target`` is empty, fall back to the first
    writable source. Raises ``CurateError`` otherwise — this is curate's
    "graduation unavailable" surface.
    """
    if not target:
        writable = settings.writable_sources
        if not writable:
            raise CurateError(
                "graduation unavailable — no writable source configured. "
                "Register the canonical knowledge_docs tree as a writable source first."
            )
        resolved = Path(writable[0]).resolve()
    else:
        resolved = Path(target).expanduser().resolve()

    if str(resolved) not in [str(Path(s).resolve()) for s in settings.sources]:
        raise CurateError(
            f"'{target}' is not a configured source. "
            f"Writable sources: {settings.writable_sources}"
        )
    if not settings.is_source_writable(str(resolved)):
        raise CurateError(f"target '{resolved}' is read-only")
    if not resolved.is_dir():
        raise CurateError(f"target directory does not exist: {resolved}")
    return resolved


def _relative_dest(taxonomy_slot: str, title: str) -> str:
    """Compute the doc path relative to the target source.

    A slot ending in ``.md`` is treated as a full relative path; otherwise
    it's a directory and the filename is derived from the title slug.
    """
    slot = taxonomy_slot.strip().strip("/")
    if slot.endswith(".md"):
        return slot
    fname = f"{slugify(title)}.md"
    return f"{slot}/{fname}" if slot else fname


def _assert_indexable(dest: Path, settings: Settings) -> None:
    """Refuse a destination that matches ``global_ignore``.

    A file under an ignored segment is written but never indexed — it would
    silently break the compounding loop (the next run's search can't match
    it). Mirrors the indexer's ``fnmatch`` matching on the absolute path.
    """
    abs_path = str(dest.resolve())
    for pattern in settings.global_ignore:
        if fnmatch.fnmatch(abs_path, pattern):
            raise CurateError(
                f"destination matches global_ignore pattern '{pattern}' — the file "
                f"would be written but never indexed, breaking the compounding loop. "
                f"Choose a taxonomy_slot outside ignored paths."
            )


def _build_document(draft: dict) -> str:
    """Assemble the final markdown — provenance frontmatter + body."""
    now = datetime.now(timezone.utc)
    parts: list[str] = ["---", f"date: {now.strftime('%Y-%m-%d')}", "promoted_from: curate"]
    if draft.get("source_type"):
        parts.append(f"source_type: {draft['source_type']}")
    if draft.get("source_ref"):
        parts.append(f"source_ref: {draft['source_ref']!r}")
    if draft.get("run_id"):
        parts.append(f"curate_run: {draft['run_id']!r}")
    if draft.get("taxonomy_slot"):
        parts.append(f"taxonomy_slot: {draft['taxonomy_slot']!r}")
    parts.extend(["---", ""])
    parts.append(draft["body_md"].strip())
    return "\n".join(parts) + "\n"


def _append_log(target_dir: Path, detail: str) -> Path:
    """Append a chronological entry to the target's log.md (curate verb)."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = f"\n## [{ts}] curate-graduate | {detail}\n"
    dest = target_dir / "log.md"
    with _curate_log_lock:
        if dest.exists():
            existing = dest.read_text(encoding="utf-8")
            if not existing.endswith("\n"):
                existing += "\n"
        else:
            existing = "# Curate Log\n\nChronological record of graduated drafts.\n"
        dest.write_text(existing + entry, encoding="utf-8")
    return dest


def graduate(
    *,
    curatedb: CurateDB,
    settings: Settings,
    draft_id: str,
    target_source: str = "",
    overwrite: bool = False,
    versioning_manager=None,
) -> dict:
    """Graduate a draft into the canonical corpus (the gated promote).

    Resolves a writable target, writes the document at the taxonomy slot
    with provenance frontmatter, appends to log.md, version-commits, and
    marks the draft ``graduated``. Raises ``CurateError`` on any gate
    failure (no writable target, read-only, ignored path, already-graduated,
    file collision without ``overwrite``).
    """
    draft = curatedb.get(draft_id)
    if not draft:
        raise CurateError(f"draft not found: {draft_id}")
    if draft["status"] != "draft":
        raise CurateError(
            f"draft {draft_id} is already {draft['status']} — only open drafts graduate"
        )

    target_dir = _resolve_writable_target(settings, target_source)
    rel = _relative_dest(draft["taxonomy_slot"], draft["title"])
    if ".." in Path(rel).parts:
        raise CurateError("taxonomy_slot may not contain '..'")
    dest = target_dir / rel
    _assert_indexable(dest, settings)

    if dest.exists() and not overwrite:
        raise CurateError(
            f"a document already exists at {rel} — pass overwrite=true to replace it"
        )

    body = _build_document(draft)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")

    log_path = _append_log(
        target_dir,
        f"{draft['title']} (from {draft.get('source_type') or 'source'}:{draft.get('source_ref') or '?'})",
    )

    logger.info("curate: graduated %s -> %s", draft_id, dest)

    paths = [rel, str(log_path.relative_to(target_dir))]
    version_commit = None
    if versioning_manager is not None:
        from app.versioning.hooks import try_commit
        version_commit = try_commit(
            settings, versioning_manager, target_dir,
            paths=paths,
            message=f"curate: graduate {draft['title']}",
        )

    curatedb.update(draft_id, status="graduated", graduated_path=str(dest))

    return {
        "status": "graduated",
        "draft_id": draft_id,
        "path": str(dest),
        "relative_path": rel,
        "target_source": str(target_dir),
        "log_path": str(log_path),
        "version_commit": version_commit,
    }


# -- reject ------------------------------------------------------------------

def reject(*, curatedb: CurateDB, draft_id: str, reason: str = "") -> dict:
    """Mark a draft ``rejected``. Kept for provenance, never written."""
    draft = curatedb.get(draft_id)
    if not draft:
        raise CurateError(f"draft not found: {draft_id}")
    if draft["status"] == "graduated":
        raise CurateError(f"draft {draft_id} was already graduated — cannot reject")
    curatedb.update(draft_id, status="rejected", reject_reason=reason.strip())
    logger.info("curate: rejected %s (%s)", draft_id, reason or "no reason")
    return {"status": "rejected", "draft_id": draft_id, "reason": reason.strip()}
