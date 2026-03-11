"""Plugin auto-discovery, registration, and management.

Each plugin lives in its own subdirectory under ``app/plugins/`` (builtin)
or ``data/plugins/`` (external / user-installed).  A valid plugin is a
package whose ``__init__.py`` exposes:

    FEATURE_FLAG: str   — name of the feature flag in settings.yaml
    router: APIRouter   — FastAPI router to include when the flag is enabled

Plugins may also include a ``plugin.yaml`` manifest providing metadata
(display name, description, icon, endpoints, config schema) that the UI
uses to render the plugin management page.

Discovery happens at import time via :func:`discover_plugins`.  Registration
is driven by :func:`register_plugins`, which checks feature flags and
includes only the routers whose flags are ``true``.
"""

import importlib
import logging
import sys
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI

from app.config import Settings

logger = logging.getLogger(__name__)

_BUILTIN_DIR = Path(__file__).resolve().parent
_EXTERNAL_DIR = Path("data/plugins")

# Module-level cache populated by discover_plugins / register_plugins
_plugin_registry: list[dict[str, Any]] = []


def _read_manifest(plugin_dir: Path) -> dict[str, Any] | None:
    """Read plugin.yaml manifest if it exists."""
    manifest_path = plugin_dir / "plugin.yaml"
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        logger.warning("Failed to read manifest for %s", plugin_dir.name, exc_info=True)
        return None


def _scan_directory(
    base_dir: Path,
    module_prefix: str,
    source: str,
) -> list[dict[str, Any]]:
    """Scan a directory for valid plugin packages."""
    plugins: list[dict[str, Any]] = []
    if not base_dir.is_dir():
        return plugins

    for child in sorted(base_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        # Skip catalogs (separate system) and __pycache__
        if child.name in ("catalogs", "__pycache__"):
            continue
        init_file = child / "__init__.py"
        if not init_file.exists():
            continue

        manifest = _read_manifest(child)

        plugins.append({
            "name": child.name,
            "module_path": f"{module_prefix}.{child.name}",
            "directory": str(child),
            "source": source,
            "manifest": manifest,
        })
    return plugins


def discover_plugins() -> list[dict[str, Any]]:
    """Scan builtin and external plugin directories.

    Returns a list of dicts with keys ``name``, ``module_path``,
    ``directory``, ``source`` (builtin|external), and ``manifest``.
    """
    plugins = _scan_directory(_BUILTIN_DIR, "app.plugins", "builtin")

    # External plugins need their parent on sys.path for imports
    ext_dir = _EXTERNAL_DIR.resolve()
    if ext_dir.is_dir():
        if str(ext_dir) not in sys.path:
            sys.path.insert(0, str(ext_dir))
        for child in sorted(ext_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("_"):
                continue
            init_file = child / "__init__.py"
            if not init_file.exists():
                continue
            manifest = _read_manifest(child)
            plugins.append({
                "name": child.name,
                "module_path": child.name,
                "directory": str(child),
                "source": "external",
                "manifest": manifest,
            })

    return plugins


def register_plugins(app: FastAPI, settings: Settings) -> list[str]:
    """Import enabled plugins and include their routers on *app*.

    Returns the names of successfully registered plugins.  Also populates
    the module-level ``_plugin_registry`` used by :func:`get_registry`.
    """
    global _plugin_registry
    registered: list[str] = []
    registry: list[dict[str, Any]] = []

    for info in discover_plugins():
        entry: dict[str, Any] = {
            **info,
            "enabled": False,
            "error": None,
        }

        # Try importing to get feature_flag (even for disabled plugins)
        try:
            mod = importlib.import_module(info["module_path"])
        except Exception as exc:
            entry["error"] = str(exc)
            logger.error(
                "Plugin '%s' failed to import — disabled due to error",
                info["name"], exc_info=True,
            )
            registry.append(entry)
            continue

        feature_flag = getattr(mod, "FEATURE_FLAG", None)
        router = getattr(mod, "router", None)
        entry["feature_flag"] = feature_flag

        # Merge manifest feature_flag if not in code
        if not feature_flag and info.get("manifest"):
            feature_flag = info["manifest"].get("feature_flag")
            entry["feature_flag"] = feature_flag

        if router is None:
            logger.debug("Plugin '%s' has no router — skipping", info["name"])
            registry.append(entry)
            continue

        enabled = feature_flag and settings.feature_enabled(feature_flag)
        entry["enabled"] = bool(enabled)

        if not enabled:
            logger.debug(
                "Plugin '%s' disabled (flag '%s' is off)",
                info["name"], feature_flag,
            )
            registry.append(entry)
            continue

        app.include_router(router)
        registered.append(info["name"])
        logger.info("Registered plugin: %s", info["name"])
        registry.append(entry)

    _plugin_registry = registry
    return registered


def get_registry() -> list[dict[str, Any]]:
    """Return the plugin registry populated during startup."""
    return list(_plugin_registry)


def get_plugin_info(name: str) -> dict[str, Any] | None:
    """Look up a single plugin by name."""
    for entry in _plugin_registry:
        if entry["name"] == name:
            return dict(entry)
    return None
