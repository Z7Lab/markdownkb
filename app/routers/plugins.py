"""Plugin management endpoints — list, install, uninstall, configure."""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_settings
from app.plugins import get_plugin_info, get_registry
from app.ratelimit import STANDARD, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["plugins"])

_EXTERNAL_DIR = Path("data/plugins")


class InstallPluginRequest(BaseModel):
    """Request to install a plugin from a GitHub URL."""

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
    "mcp_filesystem": {
        "display_name": "MCP Filesystem",
        "description": "Allow the AI planner to explore the filesystem.",
        "icon": "folder-search",
        "category": "mcp",
    },
    "mcp_terminal": {
        "display_name": "MCP Terminal",
        "description": "Allow the AI planner to run shell commands.",
        "icon": "terminal",
        "category": "mcp",
    },
}


def _build_plugin_response(entry: dict, settings: Settings) -> dict:
    """Build a rich plugin info dict from a registry entry."""
    manifest = entry.get("manifest") or {}
    feature_flag = entry.get("feature_flag") or manifest.get("feature_flag", "")

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
        "config": settings.get_plugin_config(entry["name"]) if feature_flag else {},
        "requires": manifest.get("requires", []),
        "has_manifest": bool(manifest),
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

    # Also return core features (non-plugin toggles)
    all_flags = settings.features
    plugin_flags = {p["feature_flag"] for p in plugins if p["feature_flag"]}
    core_features = []
    for flag, enabled in all_flags.items():
        if flag in plugin_flags:
            continue
        meta = _CORE_FEATURES.get(flag, {})
        core_features.append({
            "name": flag,
            "display_name": meta.get("display_name", flag.replace("_", " ").title()),
            "description": meta.get("description", ""),
            "icon": meta.get("icon", "toggle-right"),
            "category": meta.get("category", "other"),
            "feature_flag": flag,
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


@router.post("/plugins/install")
@limiter.limit(STANDARD)
def install_plugin(
    request: Request,
    req: InstallPluginRequest,
    settings: Settings = Depends(get_settings),
):
    """Install a plugin from a GitHub URL.

    Clones the repo (or subdirectory) into data/plugins/<name>/, validates
    the plugin structure, installs requirements if present, and adds the
    feature flag to settings.  Requires a container restart to activate.
    """
    url = req.url.strip()

    # Parse GitHub URL to extract repo and optional subdirectory
    repo_url, subdir = _parse_github_url(url)
    if not repo_url:
        raise HTTPException(
            status_code=400,
            detail="Invalid URL. Provide a GitHub repository URL, e.g. "
                   "https://github.com/user/repo or "
                   "https://github.com/user/repo/tree/main/path/to/plugin",
        )

    _EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)

    # Clone to temp dir first
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(tmp_path / "repo")],
                capture_output=True, text=True, check=True, timeout=60,
            )
        except subprocess.CalledProcessError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to clone repository: {e.stderr.strip()}",
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=408, detail="Clone timed out (60s limit)")

        # Resolve the plugin source directory
        source_dir = tmp_path / "repo"
        if subdir:
            source_dir = source_dir / subdir
            if not source_dir.is_dir():
                raise HTTPException(
                    status_code=400,
                    detail=f"Subdirectory '{subdir}' not found in repository",
                )

        # Validate plugin structure
        errors = _validate_plugin(source_dir)
        if errors:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid plugin: {'; '.join(errors)}",
            )

        # Read manifest to get the plugin name
        manifest = _read_manifest_safe(source_dir)
        plugin_name = manifest.get("name", source_dir.name) if manifest else source_dir.name
        plugin_name = plugin_name.replace("-", "_")

        # Check if already installed
        dest = _EXTERNAL_DIR / plugin_name
        if dest.exists():
            raise HTTPException(
                status_code=409,
                detail=f"Plugin '{plugin_name}' is already installed. "
                       "Uninstall it first to reinstall.",
            )

        # Copy plugin to external dir
        shutil.copytree(source_dir, dest)

        # Install requirements if present
        req_file = dest / "requirements.txt"
        if req_file.exists():
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                    capture_output=True, text=True, check=True, timeout=120,
                )
            except subprocess.CalledProcessError as e:
                # Clean up on failure
                shutil.rmtree(dest, ignore_errors=True)
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to install requirements: {e.stderr.strip()[:500]}",
                )

        # Add feature flag to settings (disabled by default)
        feature_flag = ""
        if manifest and manifest.get("feature_flag"):
            feature_flag = manifest["feature_flag"]
        elif (dest / "__init__.py").exists():
            # Try to read FEATURE_FLAG from the code
            try:
                content = (dest / "__init__.py").read_text()
                for line in content.splitlines():
                    if line.strip().startswith("FEATURE_FLAG"):
                        feature_flag = line.split("=", 1)[1].strip().strip("'\"")
                        break
            except Exception:
                pass

        if feature_flag:
            features = settings.features
            if feature_flag not in features:
                features[feature_flag] = False
                settings._data["features"] = features
                settings.save()

    return {
        "status": "installed",
        "name": plugin_name,
        "feature_flag": feature_flag,
        "manifest": manifest,
        "message": "Plugin installed. Enable the feature flag and restart to activate.",
    }


@router.delete("/plugins/{name}")
@limiter.limit(STANDARD)
def uninstall_plugin(
    request: Request,
    name: str,
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
                       "Disable it via the feature flag instead.",
            )
        raise HTTPException(status_code=404, detail=f"External plugin '{name}' not found")

    # Remove the feature flag from settings
    feature_flag = ""
    if entry:
        feature_flag = entry.get("feature_flag", "")
    if not feature_flag:
        manifest = _read_manifest_safe(plugin_dir)
        if manifest:
            feature_flag = manifest.get("feature_flag", "")

    if feature_flag:
        features = settings.features
        features.pop(feature_flag, None)
        settings._data["features"] = features
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
    repo_url = f"https://github.com/{user}/{repo}.git"

    # Check for /tree/branch/path subdirectory
    subdir = None
    if len(parts) > 3 and parts[2] == "tree":
        # parts[3] is the branch, rest is path
        subdir = "/".join(parts[4:]) if len(parts) > 4 else None

    return repo_url, subdir


def _validate_plugin(plugin_dir: Path) -> list[str]:
    """Validate that a directory contains a valid mdkb plugin.

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
    except Exception:
        return None
