"""Wiki Compile plugin HTTP surface.

v2 adds named, managed wikis as a first-class concept. A wiki is a
(name, path) pair tracked in WikiDB. The ingest endpoint can address a
wiki by name (`wiki`) or by raw path (`target_source`, kept for
back-compatibility with v1 callers).

Managed-wiki creation mirrors the bucket pattern:
- Default-path wikis land under ``{data_directory}/wikis/<name>/`` —
  no extra Docker mount needed (data_dir is already mounted).
- Custom-path wikis outside the project/data dir auto-add to
  ``compose.override.yml`` via the same machinery buckets use.
  A restart is required for the new bind mount to take effect; the
  response flags it via ``docker_restart_required: true``.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings
from app.config.docker import in_docker, write_compose_override
from app.deps import get_retriever, get_settings, get_versioning_manager
from app.rag.retriever import Retriever
from app.ratelimit import LLM, STANDARD, limiter
from app.plugins.wiki_compile.service import WikiCompileError, ingest
from app.plugins.wiki_compile.wikidb import WikiDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/wiki-compile", tags=["wiki_compile"])


# -- Request models ---------------------------------------------------------

class IngestRequest(BaseModel):
    source_path: str = Field(..., min_length=1, description="Absolute path to a source file to ingest")
    wiki: str = Field(..., min_length=1, description="Managed wiki name (resolved via WikiDB)")
    force: bool = Field(False, description="Overwrite existing summary page if present")


class CreateWikiRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    path: str | None = Field(
        None,
        description="Override path. Defaults to {data_directory}/wikis/{name} when omitted.",
    )


# -- Helpers ----------------------------------------------------------------

def _get_wikidb(request: Request) -> WikiDB:
    wikidb = getattr(request.app.state, "wikidb", None)
    if wikidb is None:
        raise HTTPException(503, "WikiDB not initialized — plugin may be disabled")
    return wikidb


def _default_wiki_path(settings: Settings, name: str) -> Path:
    """Default path under the data directory — mounted already, no restart."""
    return Path(settings.data_directory) / "wikis" / name


def _sync_wiki_compose(settings: Settings, wikidb: WikiDB) -> bool:
    """Regenerate compose.override.yml including all wiki paths that need mounts.

    Wikis whose path lives under project_root or data_directory are already
    mounted and don't need an entry. Custom paths outside those need adding.
    Mirrors the bucket-sync pattern; returns True if the file changed.
    """
    if not in_docker():
        return False
    try:
        project_root = settings.project_root
        wiki_configs = _wiki_mount_configs(wikidb)
        all_configs = (
            settings.source_configs
            + settings.project_root_source_configs
            + settings.bucket_mount_configs
            + wiki_configs
        )
        return write_compose_override(all_configs, project_root)
    except Exception:
        logger.debug("Could not sync compose.override.yml for wikis", exc_info=True)
        return False


def _wiki_mount_configs(wikidb: WikiDB) -> list[dict]:
    """Return source-config entries for every wiki path.

    Writable: True — wikis are derived-tier, the plugin writes to them.
    The compose writer already skips paths under project_root or data_dir,
    so default-path wikis don't produce duplicate mount entries.
    """
    return [{"path": w["path"], "writable": True} for w in wikidb.list_all()]


# -- Endpoints: management ---------------------------------------------------

@router.get("/wikis")
@limiter.limit(STANDARD)
def list_wikis(
    request: Request,
    wikidb: WikiDB = Depends(_get_wikidb),
):
    """List all managed wikis."""
    wikis = wikidb.list_all()
    return {"wikis": wikis, "total": len(wikis)}


@router.post("/wikis")
@limiter.limit(STANDARD)
def create_wiki(
    request: Request,
    req: CreateWikiRequest,
    settings: Settings = Depends(get_settings),
    wikidb: WikiDB = Depends(_get_wikidb),
):
    """Create a new managed wiki.

    If `path` is omitted, uses the default location under the data
    directory (no Docker restart needed — it's already mounted). If
    `path` is a custom location outside the project/data dir, the
    compose.override.yml gets updated and the response flags that a
    restart is required for the new mount to take effect.
    """
    if wikidb.name_exists(req.name):
        raise HTTPException(409, f"Wiki name already exists: {req.name}")

    if req.path:
        path = Path(req.path).expanduser().resolve()
    else:
        path = _default_wiki_path(settings, req.name)

    # Ensure the directory exists on disk so the indexer can watch it and
    # the LLM output has somewhere to land. parents=True handles nested
    # default locations like {data_dir}/wikis/<name>.
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(500, f"Could not create wiki directory: {e}") from e

    try:
        record = wikidb.create(req.name, str(path))
    except ValueError as e:
        raise HTTPException(409, str(e)) from e

    # Register the path as a writable source so the indexer picks it up
    # and the three-tier write-protection (service.resolve_writable_target)
    # accepts it as a valid ingest target. Write the canonical dict shape
    # (settings.add_source stores a bare string, which breaks source_configs
    # — so we append the dict directly, matching how existing sources are
    # written in settings.yaml).
    if str(path) not in settings.explicit_sources:
        settings.add_source({"path": str(path), "writable": True})
        settings.save()

    docker_restart_required = _sync_wiki_compose(settings, wikidb)

    logger.info("wiki created: name=%s path=%s", req.name, path)
    return {**record, "docker_restart_required": docker_restart_required}


@router.delete("/wikis/{name}")
@limiter.limit(STANDARD)
def delete_wiki(
    request: Request,
    name: str,
    settings: Settings = Depends(get_settings),
    wikidb: WikiDB = Depends(_get_wikidb),
):
    """Deregister a wiki. The directory on disk is NOT deleted —
    removing requires an explicit filesystem action by the user.
    """
    wiki = wikidb.get_by_name(name)
    if not wiki:
        raise HTTPException(404, f"Wiki not found: {name}")

    wikidb.delete(name)

    # Remove the path from configured sources.
    if wiki["path"] in settings.explicit_sources:
        settings.remove_source(wiki["path"])
        settings.save()

    docker_restart_required = _sync_wiki_compose(settings, wikidb)

    return {
        "status": "deregistered",
        "name": name,
        "path": wiki["path"],
        "directory_preserved": True,
        "docker_restart_required": docker_restart_required,
    }


# -- Endpoints: ingest -------------------------------------------------------

@router.post("/ingest")
@limiter.limit(LLM)
def ingest_endpoint(
    request: Request,
    req: IngestRequest,
    settings: Settings = Depends(get_settings),
    retriever: Retriever = Depends(get_retriever),
    wikidb: WikiDB = Depends(_get_wikidb),
    versioning_manager=Depends(get_versioning_manager),
):
    """Run one ingest pass (read source + LLM summary + index/log update).

    The retriever fetches existing related pages from the target wiki
    and passes them as context so the new summary can note overlaps,
    extensions, and contradictions with existing material.
    """
    wiki = wikidb.get_by_name(req.wiki)
    if not wiki:
        raise HTTPException(status_code=404, detail=f"Wiki not found: {req.wiki}")

    try:
        result = ingest(
            source_path=req.source_path,
            target_source=wiki["path"],
            settings=settings,
            retriever=retriever,
            force=req.force,
            versioning_manager=versioning_manager,
        )
    except WikiCompileError as e:
        logger.warning("wiki_compile rejected: %s", e)
        raise HTTPException(status_code=400, detail="Wiki compile failed — check server logs")
    except FileNotFoundError as e:
        logger.warning("wiki_compile source missing: %s", e)
        raise HTTPException(status_code=404, detail="Source path not found")
    except RuntimeError as e:
        logger.error("wiki_compile ingest LLM error: %s", e)
        raise HTTPException(status_code=503, detail="LLM request failed — check server logs")

    # Update WikiDB's last_ingest_at and page_count so the UI can surface them.
    try:
        target = Path(result["target_source"])
        summaries_dir = target / "summaries"
        page_count = len(list(summaries_dir.glob("*.md"))) if summaries_dir.exists() else 0
        wikidb.touch_ingest(req.wiki, page_count)
    except Exception:
        logger.debug("Could not update wiki last_ingest_at/page_count", exc_info=True)
    result["wiki"] = req.wiki
    return result
