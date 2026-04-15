"""MCP tool: create a managed wiki.

Thin wrapper over the HTTP POST /api/v1/wiki-compile/wikis endpoint — both
delegate to the same underlying logic via the plugin's WikiDB and
compose-override machinery.
"""

from pathlib import Path

from app.config import Settings
from app.config.docker import in_docker, write_compose_override

TOOL = {
    "name": "wiki_compile_create",
    "feature_flag": None,
    "requires_plugin": "wiki_compile",
    "write": True,
}

_mcp = None  # Injected by register_tools()


def handler(name: str, path: str | None = None) -> dict:
    """Create a managed wiki and register it as a writable source.

    Args:
        name: Unique wiki name. Used by ``wiki_compile_ingest``'s
              ``wiki`` argument.
        path: Optional override path. Defaults to
              ``{data_directory}/wikis/{name}`` when omitted — that
              location is inside the existing data-dir mount, so no
              Docker restart is needed. A custom path outside the
              project/data dir gets added to compose.override.yml and
              the response flags ``docker_restart_required: true``.

    Returns:
        Dict with the wiki record plus ``docker_restart_required``.
    """
    ctx = _mcp.get_context()
    settings: Settings = ctx.request_context.lifespan_context["settings"]
    wikidb = ctx.request_context.lifespan_context.get("wikidb")
    if wikidb is None:
        raise ValueError("wiki_compile plugin is disabled")

    if wikidb.name_exists(name):
        raise ValueError(f"Wiki name already exists: {name}")

    target = Path(path).expanduser().resolve() if path else (
        Path(settings.data_directory) / "wikis" / name
    )
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ValueError(f"Could not create wiki directory: {e}") from e

    record = wikidb.create(name, str(target))

    if str(target) not in settings.explicit_sources:
        raw_sources = settings._data.setdefault("sources", [])
        raw_sources.append({"path": str(target), "writable": True})
        settings.save()

    docker_restart_required = False
    if in_docker():
        try:
            project_root = settings._path.resolve().parent.parent
            wiki_configs = [{"path": w["path"], "writable": True} for w in wikidb.list_all()]
            all_configs = (
                settings.source_configs
                + settings.project_root_source_configs
                + settings.bucket_mount_configs
                + wiki_configs
            )
            docker_restart_required = write_compose_override(all_configs, project_root)
        except Exception:
            pass

    return {**record, "docker_restart_required": docker_restart_required}
