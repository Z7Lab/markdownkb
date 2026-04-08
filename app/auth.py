"""API key authentication middleware.

When an API key is configured (via ``secrets/markdownkb_api_key`` Docker
secret or ``MARKDOWNKB_API_KEY`` env var), every request must include the
header::

    X-MarkdownKB-Key: <key>

Requests without a valid key receive a **401 Unauthorized** response.
If no key is configured, authentication is silently disabled.
"""

import hmac
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

_HEADER = "X-MarkdownKB-Key"

# Paths that bypass authentication (health check, CORS preflight)
_PUBLIC_PATHS = frozenset({"/api/health", "/api/setup/generate-key"})


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Reject requests that lack a valid API key header."""

    def __init__(self, app, api_key: str):
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next):
        # OPTIONS (CORS preflight) and public paths are always allowed
        if request.method == "OPTIONS" or request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # Non-API paths (frontend static files) are allowed
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        provided = request.headers.get(_HEADER, "")
        if not hmac.compare_digest(provided, self._api_key):
            return JSONResponse(
                {"detail": "Invalid or missing API key"},
                status_code=401,
            )

        return await call_next(request)
