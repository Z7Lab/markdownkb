"""MCP tool: deregister a managed wiki.

The directory on disk is preserved — removing the files is an explicit
filesystem action the user does themselves. This mirrors the bucket
delete pattern (data is preserved; only the registration is removed).
"""

import logging

from app.config import Settings
from app.config.docker import in_docker, write_compose_override

logger = logging.getLogger(__name__)

TOOL = {
    "name": "wiki_compile_delete",
    "feature_flag": None,
    "requires_plugin": "wiki_compile",
    "write": True,
}

_mcp = None  # Injected by register_tools()


def handler(name: str) -> dict:
    """Deregister a managed wiki by name.

    Removes the WikiDB row and the corresponding ``writable: true``
    source entry from settings. The directory and its pages are left
    on disk — if the caller wants them gone, they delete the directory
    themselves.

    Args:
        name: Wiki name (from ``wiki_compile_list``).

    Returns:
        Dict with status, name, path, directory_preserved: True, and
        docker_restart_required: bool.
    """
    ctx = _mcp.get_context()
    settings: Settings = ctx.request_context.lifespan_context["settings"]
    wikidb = ctx.request_context.lifespan_context.get("wikidb")
    if wikidb is None:
        raise ValueError("wiki_compile plugin is disabled")

    record = wikidb.get_by_name(name)
    if not record:
        raise ValueError(f"Wiki not found: {name}")

    wikidb.delete(name)

    # Drop the path from configured sources.
    if record["path"] in settings.explicit_sources:
        settings.remove_source(record["path"])
        settings.save()

    docker_restart_required = False
    if in_docker():
        try:
            project_root = settings.project_root
            wiki_configs = [{"path": w["path"], "writable": True} for w in wikidb.list_all()]
            all_configs = (
                settings.source_configs
                + settings.project_root_source_configs
                + settings.bucket_mount_configs
                + wiki_configs
            )
            docker_restart_required = write_compose_override(all_configs, project_root)
        except Exception:
            logger.exception("Failed to write compose override for wiki delete; docker_restart_required will be False")

    return {
        "status": "deregistered",
        "name": name,
        "path": record["path"],
        "directory_preserved": True,
        "docker_restart_required": docker_restart_required,
    }
