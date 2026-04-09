"""Plugin management endpoints — list, install, uninstall, configure."""

import logging
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings, default_data_dir as _data_dir
from app.deps import get_settings, require_auth
from app.plugins import get_plugin_info, get_registry
from app.ratelimit import STANDARD, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["plugins"])

_EXTERNAL_DIR = Path(_data_dir()) / "plugins"


class InstallPluginRequest(BaseModel):
    """Request to install a plugin from a GitHub URL or local directory path."""

    url: str = Field(..., min_length=1, max_length=500)


class UninstallPluginRequest(BaseModel):
    """Request to uninstall an external plugin."""

    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")


# -- Core feature metadata (non-plugin toggles) --

_CORE_FEATURES = {
    "rag_chat": {
        "display_name": "RAG Chat",
        "description": "Retrieval-augmented chat with your documents.",
        "icon": "message-square",
        "category": "core",
    },
    "file_watcher": {
        "display_name": "File Watcher",
        "description": "Automatically re-index files when they change on disk.",
        "icon": "eye",
        "category": "core",
    },
    "deep_research": {
        "display_name": "Deep Research",
        "description": "MCTS-powered multi-angle research synthesis for search summaries.",
        "icon": "microscope",
        "category": "ai",
    },
    "agent_skills": {
        "display_name": "Agent Skills",
        "description": "Custom skill scripts for the planner agent.",
        "icon": "wand-2",
        "category": "ai",
    },
    "diagnostics": {
        "display_name": "Diagnostics",
        "description": "Internal diagnostics and debug endpoints.",
        "icon": "stethoscope",
        "category": "advanced",
    },
    "rate_limiting": {
        "display_name": "Rate Limiting",
        "description": "Enforce per-endpoint rate limits.",
        "icon": "gauge",
        "category": "advanced",
    },
}


def _check_system_dependencies(manifest: dict) -> list[dict]:
    """Check system_dependencies from a plugin manifest.

    Returns a list of dependency status dicts with keys:
    name, binary, required, available, install_hint.
    """
    import shutil

    deps = manifest.get("system_dependencies", [])
    if not deps:
        return []

    results = []
    for dep in deps:
        binary = dep.get("binary", "")
        results.append({
            "name": dep.get("name", binary),
            "binary": binary,
            "required": dep.get("required", True),
            "available": shutil.which(binary) is not None if binary else False,
            "install_hint": dep.get("install_hint", ""),
        })
    return results


def _build_plugin_response(entry: dict, settings: Settings) -> dict:
    """Build a rich plugin info dict from a registry entry."""
    manifest = entry.get("manifest") or {}
    feature_flag = entry.get("feature_flag") or manifest.get("feature_flag", "")

    dep_status = _check_system_dependencies(manifest)
    missing_required = [d for d in dep_status if d["required"] and not d["available"]]

    result = {
        "name": entry["name"],
        "display_name": manifest.get("display_name", entry["name"].replace("_", " ").title()),
        "description": manifest.get("description", ""),
        "version": manifest.get("version", ""),
        "author": manifest.get("author", ""),
        "icon": manifest.get("icon", "puzzle"),
        "category": manifest.get("category", "other"),
        "feature_flag": feature_flag,
        "enabled": entry.get("enabled", False),
        "source": entry.get("source", "builtin"),
        "error": entry.get("error"),
        "endpoints": manifest.get("endpoints", []),
        "config_schema": manifest.get("config", {}),
        "config": settings.get_plugin_config(entry["name"]),
        "requires": manifest.get("requires", []),
        "has_manifest": bool(manifest),
        "system_dependencies": dep_status,
        "dependencies_met": len(missing_required) == 0,
    }
    return result


@router.get("/plugins")
@limiter.limit(STANDARD)
def list_plugins(
    request: Request,
    settings: Settings = Depends(get_settings),
):
    """List all discovered plugins (builtin + external) with their manifests."""
    registry = get_registry()
    plugins = [_build_plugin_response(entry, settings) for entry in registry]

    # Build core + MCP feature list for the UI
    core_features = []
    for flag, enabled in settings.core_features.items():
        meta = _CORE_FEATURES.get(flag, {})
        core_features.append({
            "name": flag,
            "display_name": meta.get("display_name", flag.replace("_", " ").title()),
            "description": meta.get("description", ""),
            "icon": meta.get("icon", "toggle-right"),
            "category": meta.get("category", "core"),
            "section": "core",
            "enabled": enabled,
        })
    for flag, enabled in settings.mcp_features.items():
        # MCP features use mcp_ prefix keys in _CORE_FEATURES metadata
        meta_key = f"mcp_{flag}"
        meta = _CORE_FEATURES.get(meta_key, {})
        core_features.append({
            "name": flag,
            "display_name": meta.get("display_name", flag.replace("_", " ").title()),
            "description": meta.get("description", ""),
            "icon": meta.get("icon", "toggle-right"),
            "category": meta.get("category", "mcp"),
            "section": "mcp",
            "enabled": enabled,
        })

    return {"plugins": plugins, "core_features": core_features}


@router.get("/plugins/{name}")
@limiter.limit(STANDARD)
def get_plugin(
    request: Request,
    name: str,
    settings: Settings = Depends(get_settings),
):
    """Get details for a specific plugin."""
    entry = get_plugin_info(name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    return _build_plugin_response(entry, settings)


def _install_from_source(source_dir: Path, settings: Settings) -> dict:
    """Validate, copy, and register a plugin from a source directory.

    Shared by both GitHub and local-path install flows.  Returns the
    response dict on success; raises HTTPException on failure.
    """
    errors = _validate_plugin(source_dir)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plugin: {'; '.join(errors)}",
        )

    manifest = _read_manifest_safe(source_dir)
    plugin_name = manifest.get("name", source_dir.name) if manifest else source_dir.name
    plugin_name = plugin_name.replace("-", "_")

    dest = _EXTERNAL_DIR / plugin_name
    if dest.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Plugin '{plugin_name}' is already installed. "
                   "Uninstall it first to reinstall.",
        )

    shutil.copytree(source_dir, dest)

    # Install requirements if present.
    # Use --only-binary :all: to prevent execution of untrusted setup.py
    # scripts from source distributions.
    req_file = dest / "requirements.txt"
    if req_file.exists():
        try:
            subprocess.run(
                [
                    sys.executable, "-m", "pip", "install",
                    "-r", str(req_file),
                    "--only-binary", ":all:",
                ],
                capture_output=True, text=True, check=True, timeout=120,
            )
        except subprocess.CalledProcessError as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise HTTPException(
                status_code=400,
                detail=f"Failed to install requirements: {e.stderr.strip()[:500]}",
            )

    # Register the plugin as disabled in plugins.<name>.enabled
    if not settings.plugin_enabled(plugin_name):
        settings.set_plugin_enabled(plugin_name, False)
        settings.save()

    return {
        "status": "installed",
        "name": plugin_name,
        "manifest": manifest,
        "message": "Plugin installed. Enable it in settings and restart to activate.",
    }


def _is_local_path(url: str) -> bool:
    """Check if the URL looks like a local filesystem path."""
    return url.startswith("/") or url.startswith("./") or url.startswith("../")


@router.post("/plugins/install")
@limiter.limit(STANDARD)
def install_plugin(
    request: Request,
    req: InstallPluginRequest,
    _auth: None = Depends(require_auth),
    settings: Settings = Depends(get_settings),
):
    """Install a plugin from a GitHub URL or local directory path.

    Accepts GitHub URLs (clones the repo) or local absolute/relative paths
    (copies the directory).  Validates plugin structure, installs requirements
    if present, and adds the feature flag to settings.  Requires a container
    restart to activate.
    """
    url = req.url.strip()
    _EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)

    # --- Local directory path ---
    if _is_local_path(url):
        source_dir = Path(url).resolve()
        if not source_dir.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"Directory not found: {source_dir}",
            )
        return _install_from_source(source_dir, settings)

    # --- GitHub URL ---
    repo_url, subdir = _parse_github_url(url)
    if not repo_url:
        raise HTTPException(
            status_code=400,
            detail="Invalid source. Provide a GitHub URL "
                   "(e.g. https://github.com/user/repo) or a local directory path "
                   "(e.g. /path/to/plugin or ./my-plugin).",
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(tmp_path / "repo")],
                capture_output=True, text=True, check=True, timeout=60,
            )
        except subprocess.CalledProcessError as e:
            logger.warning("git clone failed: %s", e.stderr.strip())
            raise HTTPException(
                status_code=400,
                detail="Failed to clone repository. Check the URL and try again.",
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=408, detail="Clone timed out (60s limit)")

        source_dir = tmp_path / "repo"
        if subdir:
            source_dir = source_dir / subdir
            if not source_dir.is_dir():
                raise HTTPException(
                    status_code=400,
                    detail=f"Subdirectory '{subdir}' not found in repository",
                )

        return _install_from_source(source_dir, settings)


@router.delete("/plugins/{name}")
@limiter.limit(STANDARD)
def uninstall_plugin(
    request: Request,
    name: str,
    _auth: None = Depends(require_auth),
    settings: Settings = Depends(get_settings),
):
    """Uninstall an external plugin.

    Only external (user-installed) plugins can be uninstalled.
    Builtin plugins are part of the application and cannot be removed.
    """
    entry = get_plugin_info(name)

    # Check if it's an external plugin in data/plugins/
    plugin_dir = _EXTERNAL_DIR / name
    if not plugin_dir.is_dir():
        if entry and entry.get("source") == "builtin":
            raise HTTPException(
                status_code=400,
                detail=f"Plugin '{name}' is a builtin plugin and cannot be uninstalled. "
                       "Disable it in settings instead.",
            )
        raise HTTPException(status_code=404, detail=f"External plugin '{name}' not found")

    # Remove the plugin's config section entirely
    settings.remove_plugin_config(name)
    settings.save()

    # Remove the plugin directory
    shutil.rmtree(plugin_dir)

    return {
        "status": "uninstalled",
        "name": name,
        "message": "Plugin removed. Restart to complete cleanup.",
    }


def _parse_github_url(url: str) -> tuple[str | None, str | None]:
    """Parse a GitHub URL into (repo_clone_url, subdirectory).

    Supports:
    - https://github.com/user/repo
    - https://github.com/user/repo/tree/branch/path/to/plugin
    - github.com/user/repo
    - user/repo (assumes github.com)
    """
    url = url.strip().rstrip("/")

    # Strip protocol
    clean = url
    for prefix in ("https://", "http://", "git://"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
            break

    # Handle "user/repo" shorthand
    if "/" in clean and "." not in clean.split("/")[0]:
        clean = f"github.com/{clean}"

    if not clean.startswith("github.com/"):
        return None, None

    parts = clean.removeprefix("github.com/").split("/")
    if len(parts) < 2:
        return None, None

    user, repo = parts[0], parts[1]
    # Validate user/repo contain only safe characters
    if not re.match(r'^[a-zA-Z0-9._-]+$', user) or not re.match(r'^[a-zA-Z0-9._-]+$', repo):
        return None, None
    repo_url = f"https://github.com/{user}/{repo}.git"

    # Check for /tree/branch/path subdirectory
    subdir = None
    if len(parts) > 3 and parts[2] == "tree":
        # parts[3] is the branch, rest is path
        subdir = "/".join(parts[4:]) if len(parts) > 4 else None

    return repo_url, subdir


def _validate_plugin(plugin_dir: Path) -> list[str]:
    """Validate that a directory contains a valid MarkdownKB plugin.

    Returns a list of error messages (empty = valid).
    """
    errors: list[str] = []

    init_file = plugin_dir / "__init__.py"
    if not init_file.exists():
        errors.append("Missing __init__.py")
        return errors

    content = init_file.read_text()

    # Check for FEATURE_FLAG
    if "FEATURE_FLAG" not in content:
        manifest = _read_manifest_safe(plugin_dir)
        if not manifest or not manifest.get("feature_flag"):
            errors.append(
                "Missing FEATURE_FLAG in __init__.py or feature_flag in plugin.yaml"
            )

    # Check for router
    if "router" not in content:
        errors.append("Missing 'router' export in __init__.py")

    # Check for plugin.yaml (recommended but not required)
    if not (plugin_dir / "plugin.yaml").exists():
        logger.info(
            "Plugin '%s' has no plugin.yaml — metadata will be limited",
            plugin_dir.name,
        )

    return errors


def _read_manifest_safe(plugin_dir: Path) -> dict | None:
    """Read plugin.yaml without raising."""
    manifest_path = plugin_dir / "plugin.yaml"
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        logger.warning("Failed to read manifest for %s", plugin_dir.name, exc_info=True)
        return None
