"""One-time setup endpoints — API key generation for network-exposed instances."""

import logging
import secrets

from fastapi import APIRouter, HTTPException, Request

from app.ratelimit import STANDARD, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/setup", tags=["setup"])

from app.config import _data_secrets_dir


@router.post("/generate-key")
@limiter.limit(STANDARD)
def generate_key(request: Request):
    """Generate an API key and persist it.

    Only works when no API key is currently configured and only when the
    request originates from localhost, so that a LAN attacker cannot be
    first-caller and lock out the legitimate owner.  Returns the generated
    key once — it is not retrievable after this response.  The key is
    written to data/secrets/ (writable volume) and picked up by
    _read_secret on subsequent requests and restarts.
    """
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Key generation is only allowed from localhost")

    if getattr(request.app.state, "auth_enabled", False):
        raise HTTPException(403, "API key already configured")

    key = secrets.token_urlsafe(32)

    target = _data_secrets_dir() / "markdownkb_api_key"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(key)
        logger.info("Generated API key, written to %s", target)
    except OSError as e:
        logger.error("Failed to write API key to %s: %s", target, e)
        raise HTTPException(500, "Failed to persist API key")

    # Enable auth on the running instance by updating app state.
    # ApiKeyMiddleware reads app.state.api_key on every request, so no
    # middleware rebuild is needed.
    request.app.state.api_key = key
    request.app.state.auth_enabled = True

    return {"api_key": key, "status": "configured"}
