"""Plugin auto-discovery and registration.

Each plugin lives in its own subdirectory under ``app/plugins/``.  A valid
plugin is a package whose ``__init__.py`` exposes:

    FEATURE_FLAG: str   — name of the feature flag in settings.yaml
    router: APIRouter   — FastAPI router to include when the flag is enabled

Discovery happens at import time via :func:`discover_plugins`.  Registration
is driven by :func:`register_plugins`, which checks feature flags and
includes only the routers whose flags are ``true``.
"""

import importlib
import logging
from pathlib import Path

from fastapi import FastAPI

from app.config import Settings

logger = logging.getLogger(__name__)

_PLUGINS_DIR = Path(__file__).resolve().parent


def discover_plugins() -> list[dict]:
    """Scan the plugins directory and return metadata for each valid plugin.

    Returns a list of dicts with keys ``name``, ``feature_flag``, and
    ``module_path`` (dotted import path).  Importing the actual module is
    deferred to :func:`register_plugins` so that a missing dependency in a
    disabled plugin never crashes the app.
    """
    plugins: list[dict] = []
    for child in sorted(_PLUGINS_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        init_file = child / "__init__.py"
        if not init_file.exists():
            continue
        plugins.append({
            "name": child.name,
            "module_path": f"app.plugins.{child.name}",
        })
    return plugins


def register_plugins(app: FastAPI, settings: Settings) -> list[str]:
    """Import enabled plugins and include their routers on *app*.

    Returns the names of successfully registered plugins.
    """
    registered: list[str] = []

    for info in discover_plugins():
        try:
            mod = importlib.import_module(info["module_path"])
        except Exception:
            logger.error(
                "Plugin '%s' failed to import — disabled due to error",
                info["name"], exc_info=True,
            )
            continue

        feature_flag = getattr(mod, "FEATURE_FLAG", None)
        router = getattr(mod, "router", None)

        if router is None:
            logger.debug("Plugin '%s' has no router — skipping", info["name"])
            continue

        if feature_flag and not settings.feature_enabled(feature_flag):
            logger.debug(
                "Plugin '%s' disabled (flag '%s' is off)",
                info["name"], feature_flag,
            )
            continue

        app.include_router(router)
        registered.append(info["name"])
        logger.info("Registered plugin: %s", info["name"])

    return registered
