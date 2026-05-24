"""Filesystem / secret / env-var helpers used by ``Settings``.

Extracted from ``app.config.__init__`` so the package's top-level module
focuses on the Settings class and its mixins. None of these helpers have
application state — they're pure functions reading env vars and files.
"""

import logging
import os
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

logger = logging.getLogger(__name__)


DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "settings.yaml"
)

SECRETS_DIR = Path(os.environ.get("MARKDOWNKB_SECRETS_DIR", "/run/secrets"))


def default_data_dir() -> str:
    """Resolve the data directory.

    Priority: ``MARKDOWNKB_DATA_DIR`` env var → platformdirs user_data_dir.
    Docker sets ``MARKDOWNKB_DATA_DIR=/data`` so the app never needs to
    know whether it's containerized.
    """
    return os.environ.get("MARKDOWNKB_DATA_DIR") or user_data_dir("markdownkb")


def data_secrets_dir() -> Path:
    """Writable secrets directory inside the data directory."""
    return Path(default_data_dir()) / "secrets"


def read_secret(name: str) -> str:
    """Read a secret by name.

    Checks ``data/secrets/`` (writable, for generated keys) first, then
    Docker's read-only secrets mount (``/run/secrets/``). Returns the
    file content (stripped) or empty string if not found or empty.
    """
    for directory in (data_secrets_dir(), SECRETS_DIR):
        path = directory / name
        try:
            if path.is_file():
                value = path.read_text().strip()
                if value:
                    return value
        except OSError as e:
            logger.warning("Failed to read secret '%s' from %s: %s", name, directory, e)
    return ""


def resolve_env(value: str) -> str:
    """Replace ``${VAR}`` placeholders with their env var values.

    Handles both whole-string (``"${VAR}"``) and inline
    (``"http://host:${PORT}/path"``) patterns.  Unset variables produce a
    warning and resolve to empty string.
    """
    if not isinstance(value, str) or "${" not in value:
        return value

    import re

    def _replace(match: re.Match) -> str:
        env_var = match.group(1)
        resolved = os.environ.get(env_var)
        if resolved is None:
            logger.warning(
                "Environment variable %s is not set (referenced in settings.yaml) — "
                "using empty string, which may disable dependent features",
                env_var,
            )
            return ""
        return resolved

    return re.sub(r"\$\{([^}]+)\}", _replace, value)


def resolve_env_recursive(obj: Any, skip_keys: frozenset[str] = frozenset()) -> Any:
    """Recursively apply :func:`resolve_env` across dicts/lists/strings.

    Resolution happens at ``Settings.__init__`` and ``Settings.reload()``
    time only — see ``Settings`` docstring for the timing contract.

    Keys in ``skip_keys`` are left untouched — their values are never
    interpolated.  Use this for fields like ``api_key`` that must always
    resolve at use time via the secrets/env lookup chain, never from YAML.
    """
    if isinstance(obj, str):
        return resolve_env(obj)
    if isinstance(obj, dict):
        return {
            k: (v if k in skip_keys else resolve_env_recursive(v, skip_keys))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [resolve_env_recursive(v, skip_keys) for v in obj]
    return obj
