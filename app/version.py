"""Single source of truth for the running mdkb version.

Reads from installed package metadata first (works when mdkb is pip-installed
or built into the Docker image), then falls back to reading ``pyproject.toml``
relative to this file (works in dev when running from a source checkout).
"""

from __future__ import annotations

import logging
import tomllib
from importlib import metadata
from pathlib import Path

logger = logging.getLogger(__name__)

_FALLBACK = "0.0.0"


def _read_pyproject() -> str | None:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version")
    except Exception:
        logger.debug("could not read version from pyproject.toml", exc_info=True)
        return None


def _resolve() -> str:
    try:
        return metadata.version("markdownkb")
    except metadata.PackageNotFoundError:
        pass
    pv = _read_pyproject()
    if pv:
        return pv
    return _FALLBACK


APP_VERSION = _resolve()
