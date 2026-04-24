"""Docker compose-override helpers for bucket source paths.

When running inside Docker, a bucket's source path must be bind-mounted
into the container for the indexer to reach it. These helpers handle
mount-set synchronization without leaking compose internals into the
HTTP handler.
"""

import json
import logging
from pathlib import Path

from app.config import Settings
from app.config.docker import in_docker, write_compose_override

from .bucket_service import BucketService

logger = logging.getLogger(__name__)


def sync_compose(settings: Settings) -> bool:
    """Regenerate compose.override.yml including all active bucket mounts.

    Returns True when the file changed (Docker restart needed for new mounts).
    """
    if not in_docker():
        return False
    try:
        project_root = settings.project_root
        all_configs = (
            settings.source_configs
            + settings.project_root_source_configs
            + settings.bucket_mount_configs
        )
        return write_compose_override(all_configs, project_root)
    except Exception:
        logger.debug("Could not sync compose.override.yml for buckets", exc_info=True)
        return False


def collect_mount_paths(svc: BucketService) -> list[str]:
    """Return the unique source paths needed for Docker mounts across all buckets."""
    paths: list[str] = []
    seen: set[str] = set()
    for bucket in svc.db.list_all():
        sources = json.loads(bucket.get("sources", "[]"))
        for src in sources:
            raw = src.get("path", "")
            if not raw:
                continue
            resolved = str(Path(raw).resolve())
            if resolved not in seen:
                seen.add(resolved)
                paths.append(resolved)
    return paths


def ensure_mounts_for_sources(
    settings: Settings,
    svc: BucketService,
    source_paths: list[str],
) -> bool:
    """Add each source path to bucket mounts and regenerate compose override.

    Called from ``create_bucket`` after the record is persisted. A path
    already covered by a mounted ``base_path`` is skipped (its parent
    bind-mount covers subdirectories).

    Returns True when a Docker restart is needed.
    """
    if not in_docker():
        return False

    base_path_str = settings.get_plugin_config("buckets").get("base_path", "")
    mounted_paths = set(settings.bucket_mounts)
    base_resolved = str(Path(base_path_str).resolve()) if base_path_str else ""
    base_mounted = bool(base_resolved and base_resolved in mounted_paths)

    changed = False
    for raw in source_paths:
        resolved = str(Path(raw).resolve())
        if not Path(resolved).exists():
            if base_mounted and (resolved == base_resolved or resolved.startswith(base_resolved + "/")):
                continue
            if settings.add_bucket_mount(resolved):
                changed = True

    if changed:
        settings.save()
        sync_compose(settings)
    return changed


def prune_mounts_after_delete(settings: Settings, svc: BucketService) -> None:
    """Reduce ``bucket_mounts`` to paths still used by remaining buckets."""
    if not in_docker():
        return
    still_needed = collect_mount_paths(svc)
    settings.set_bucket_mounts(still_needed)
    settings.save()
    sync_compose(settings)


def ensure_base_path_mount(settings: Settings, svc: BucketService, base_path: str) -> bool:
    """Mount the user-configured bucket base path. Returns True on restart-required."""
    if not in_docker():
        return False
    resolved = str(Path(base_path).resolve())
    if settings.add_bucket_mount(resolved):
        sync_compose(settings)
        return True
    return False
