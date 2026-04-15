"""Version-check subsystem: detect whether a newer mdkb release is available.

Auto-detects the install method (Docker, native pip, or dev git checkout)
and queries the appropriate source on demand.  No background polling — runs
only when the user requests it via the Settings UI.

Off by default; user opts in with ``settings.core.update_check``.
"""

from app.version_check.detector import (
    InstallMethod,
    UpdateInfo,
    detect_install_method,
    check_for_update,
)

__all__ = [
    "InstallMethod",
    "UpdateInfo",
    "detect_install_method",
    "check_for_update",
]
