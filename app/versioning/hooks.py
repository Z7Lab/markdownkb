"""Best-effort commit helpers for writers.

Callers (write_api, wiki_compile) invoke these after a successful
filesystem write. Failures never raise — versioning is a background
concern, not a correctness gate on the user's write.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import Settings
from app.versioning.git_manager import GitManager

logger = logging.getLogger(__name__)


def try_commit(
    settings: Settings,
    manager: GitManager | None,
    source_dir: str | Path,
    paths: list[str | Path],
    message: str,
) -> str | None:
    """Commit ``paths`` inside ``source_dir`` if versioning is enabled
    for that source. Swallows errors.
    """
    if manager is None or not settings.versioning_enabled:
        return None
    source = str(Path(source_dir).resolve())
    if not settings.is_source_versioned(source):
        return None
    try:
        return manager.commit(source, message, paths=paths)
    except Exception:
        logger.warning(
            "versioning: commit failed for %s (%d paths) — continuing",
            source, len(paths), exc_info=True,
        )
        return None
