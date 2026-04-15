"""HTTP API for the version-check subsystem."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from app.config import Settings
from app.deps import get_settings
from app.ratelimit import STANDARD, limiter
from app.version_check.detector import check_for_update, detect_install_method

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/version", tags=["version"])


@router.get("")
@limiter.limit(STANDARD)
def get_version(request: Request, settings: Settings = Depends(get_settings)):
    """Return the running version and install method without contacting the network."""
    return {
        "current_version": getattr(request.app, "version", "0.0.0"),
        "install_method": detect_install_method().value,
        "update_check_enabled": settings.core_enabled("update_check"),
    }


@router.get("/check")
@limiter.limit(STANDARD)
def get_check(request: Request, settings: Settings = Depends(get_settings)):
    """Query the appropriate source (PyPI / GitHub) and report.

    Returns 200 even on failure — the error lands in the response body so
    the UI can show "could not check for updates" without treating it as
    a hard error.

    Returns ``{"disabled": true}`` if the user hasn't opted in to update
    checks.  No network request is made in that case.
    """
    if not settings.core_enabled("update_check"):
        return {
            "disabled": True,
            "current_version": getattr(request.app, "version", "0.0.0"),
            "install_method": detect_install_method().value,
        }
    info = check_for_update(getattr(request.app, "version", "0.0.0"))
    return info.to_dict()
