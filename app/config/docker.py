"""Docker integration utilities — compose override generation."""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def in_docker() -> bool:
    """Detect if running inside a Docker container."""
    return os.path.exists("/.dockerenv") or os.environ.get("MARKDOWNKB_DATA_DIR") == "/data"


def generate_compose_override(source_configs: list[dict], project_root: Path) -> str:
    """Generate compose.override.yml content from source configs.

    Each source config has ``path`` (resolved) and ``writable`` (bool).
    Paths that are inside the project (./docs) or the data directory
    are skipped — they're already mounted.
    """
    data_dir = os.environ.get("MARKDOWNKB_DATA_DIR", "")
    project_str = str(project_root)

    main_volumes = []
    mcp_volumes = []

    for cfg in source_configs:
        path = cfg["path"]
        writable = cfg["writable"]

        # Skip paths already inside the project or data directory
        if path.startswith(project_str + "/") or path == project_str:
            continue
        if data_dir and (path.startswith(data_dir + "/") or path == data_dir):
            continue

        suffix = "" if writable else ":ro"
        main_volumes.append(f"      - {path}:{path}{suffix}")
        mcp_volumes.append(f"      - {path}:{path}:ro")

    lines = [
        "# Auto-generated from settings.yaml sources.",
        "# Regenerated when sources are added or removed via the UI.",
        "# After changes: make down && make up",
        "",
        "services:",
        "  markdownkb:",
        "    volumes:",
    ]
    if main_volumes:
        lines.extend(main_volumes)
    else:
        lines.append("      []")
    lines.extend([
        "",
        "  markdownkb-mcp:",
        "    volumes:",
    ])
    if mcp_volumes:
        lines.extend(mcp_volumes)
    else:
        lines.append("      []")
    lines.append("")

    return "\n".join(lines)


def write_compose_override(source_configs: list[dict], project_root: Path) -> bool:
    """Write compose.override.yml if it would change.

    Returns True if the file was written (content changed or new).
    """
    override_path = project_root / "compose.override.yml"
    content = generate_compose_override(source_configs, project_root)

    # Don't rewrite if unchanged
    if override_path.exists():
        existing = override_path.read_text()
        if existing == content:
            return False

    override_path.write_text(content)
    logger.info("Updated compose.override.yml with %d source mounts", len(source_configs))
    return True
