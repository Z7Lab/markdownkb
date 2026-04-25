"""Per-logger level overrides — merges plugin-declared defaults with user settings.

Plugin manifests may declare ``logging_overrides: {logger_name: LEVEL}`` to
silence or quiet noisy third-party loggers (e.g. pdfminer at DEBUG floods the
log with one line per PDF token). These defaults are applied automatically when
the plugin is enabled, without any core knowledge of the specific loggers.

User-defined overrides (stored in ``settings.logging.logger_overrides``) take
precedence over plugin defaults and persist across restarts.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings

_VALID_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def get_plugin_defaults() -> dict[str, dict[str, str]]:
    """Return {plugin_name: {logger_name: level}} for all enabled plugins that declare logging_overrides."""
    from app.plugins import _plugin_registry

    result: dict[str, dict[str, str]] = {}
    for p in _plugin_registry:
        if not p.get("enabled"):
            continue
        manifest = p.get("manifest") or {}
        raw = manifest.get("logging_overrides")
        if raw and isinstance(raw, dict):
            result[p["name"]] = {k: str(v).upper() for k, v in raw.items()}
    return result


def apply_log_overrides(settings: Settings) -> None:
    """Apply per-logger overrides after the root log level has been set.

    Plugin-declared defaults are applied first; user settings.logger_overrides
    take precedence so users can always tune or undo a plugin's default.
    """
    merged: dict[str, str] = {}
    for overrides in get_plugin_defaults().values():
        merged.update(overrides)
    merged.update(settings.logger_overrides)

    for name, level_str in merged.items():
        level = getattr(logging, level_str.upper(), logging.WARNING)
        logging.getLogger(name).setLevel(level)
