"""Lightweight type validation for ``settings.yaml``.

The Settings class is a hand-rolled singleton (not Pydantic ``BaseSettings``)
because it also persists YAML changes back to disk and supports mixins.
Without Pydantic's declarative schema, a misconfigured value such as
``temperature: "high"`` would only fail at use time deep inside the LLM
call path.

This module runs at ``Settings.__init__`` / ``reload`` time and checks
the small set of scalars that are easy to get wrong when hand-editing
YAML.  The goal is to fail loudly with a helpful pointer — not to
re-implement Pydantic.  Unknown keys are tolerated (forward-compat).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SettingsValidationError(ValueError):
    """Raised when settings.yaml contains a value of the wrong type."""


# (dotted key-path, expected python type or tuple of types, optional range)
# ``None`` and missing keys are always allowed — only misconfigured values
# fail.  Ranges are inclusive on both ends.
_CHECKS: list[tuple[str, tuple, tuple | None]] = [
    ("embeddings.chunk_size", (int,), (16, 8192)),
    ("embeddings.chunk_overlap", (int,), (0, 4096)),
    ("retrieval.top_k", (int,), (1, 1000)),
    ("retrieval.score_threshold", (int, float), (0.0, 1.0)),
    ("retrieval.hybrid_search", (bool,), None),
    ("retrieval.bm25_weight", (int, float), (0.0, 1.0)),
    ("llm.temperature", (int, float), (0.0, 2.0)),
    ("llm.max_tokens", (int,), (1, 1_000_000)),
    ("server.port", (int,), (1, 65535)),
    ("server.host", (str,), None),
    ("logging.level", (str,), None),
    ("ui.file_list_limit", (int,), (1, 1_000_000)),
]

# OFF is a MarkdownKB-specific value meaning "disable log emission" — it's
# already accepted by the /settings API via ``schemas.py`` and by the log
# buffer.  Accept it here too.
_ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "OFF"}


def _dig(data: dict, path: str) -> tuple[bool, Any]:
    """Return (found, value) for a dotted key path in *data*."""
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def validate(data: dict) -> None:
    """Validate *data* against the type table.

    Raises :class:`SettingsValidationError` on the first problem so the
    message points at exactly one key.  Config files can still contain
    arbitrary extra keys for mixins or plugins — we only police the
    scalars listed in ``_CHECKS``.
    """
    for key, expected_types, rng in _CHECKS:
        found, value = _dig(data, key)
        if not found or value is None:
            continue
        # bool is a subtype of int in Python; keep them distinct.
        if bool in expected_types and not isinstance(value, bool):
            raise SettingsValidationError(
                f"settings.yaml: {key} must be a boolean, got "
                f"{type(value).__name__}={value!r}"
            )
        if bool not in expected_types and isinstance(value, bool):
            raise SettingsValidationError(
                f"settings.yaml: {key} must be a number/string, got bool={value!r}"
            )
        if not isinstance(value, expected_types):
            names = " or ".join(t.__name__ for t in expected_types)
            raise SettingsValidationError(
                f"settings.yaml: {key} must be {names}, got "
                f"{type(value).__name__}={value!r}"
            )
        if rng is not None:
            lo, hi = rng
            if value < lo or value > hi:
                raise SettingsValidationError(
                    f"settings.yaml: {key}={value!r} is outside the allowed "
                    f"range [{lo}, {hi}]"
                )

    # Logging level is an enum — check it explicitly.
    found, value = _dig(data, "logging.level")
    if found and isinstance(value, str):
        if value.upper() not in _ALLOWED_LOG_LEVELS:
            raise SettingsValidationError(
                f"settings.yaml: logging.level={value!r} must be one of "
                f"{sorted(_ALLOWED_LOG_LEVELS)}"
            )
