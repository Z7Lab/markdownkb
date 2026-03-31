"""One-time setup endpoints — API key generation for network-exposed instances."""

import logging
import secrets
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from app.ratelimit import STANDARD, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/setup", tags=["setup"])

# Generated keys are written to data/secrets/ (inside the writable data volume).
# _read_secret checks this path before /run/secrets/, so the key is picked up
# on restart without needing to touch the host secrets/ directory.
_DATA_SECRETS_DIR = Path("/app/data/secrets")


@router.post("/generate-key")
@limiter.limit(STANDARD)
def generate_key(request: Request):
    """Generate an API key and persist it.

    Only works when no API key is currently configured. Returns the
    generated key once — it is not retrievable after this response.
    The key is written to data/secrets/ (writable volume) and picked
    up by _read_secret on subsequent requests and restarts.
    """
    if getattr(request.app.state, "auth_enabled", False):
        raise HTTPException(403, "API key already configured")

    key = secrets.token_urlsafe(32)

    # Write to the data volume (host ./data/secrets/)
    target = _DATA_SECRETS_DIR / "mdkb_api_key"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(key)
        logger.info("Generated API key, written to %s", target)
    except OSError as e:
        logger.error("Failed to write API key to %s: %s", target, e)
        raise HTTPException(500, "Failed to persist API key")

    # Enable auth on the running instance
    from app.auth import ApiKeyMiddleware
    request.app.add_middleware(ApiKeyMiddleware, api_key=key)
    request.app.state.auth_enabled = True

    return {"api_key": key, "status": "configured"}
