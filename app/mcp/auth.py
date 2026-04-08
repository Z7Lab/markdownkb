"""API key authentication middleware for the MCP SSE server.

Accepts auth via any of:
  1. ``X-MarkdownKB-Key`` header (same as REST API)
  2. ``?token=`` query parameter (for sandboxed agents that can't set
     headers on SSE connections — matches the pattern used by
     deliberative-ai's ephemeral token flow)

When an API key is configured, every SSE/message request must include
a valid credential via one of these methods.  If no key is configured,
the middleware is not added and all requests are allowed.
"""

import hmac
import logging
from urllib.parse import parse_qs

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

_HEADER = "X-MarkdownKB-Key"


class McpApiKeyMiddleware:
    """ASGI middleware that rejects requests without a valid API key."""

    def __init__(self, app: ASGIApp, api_key: str):
        self.app = app
        self._api_key = api_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # Check header first, then query parameter
        provided = request.headers.get(_HEADER, "")
        if not provided:
            qs = parse_qs(scope.get("query_string", b"").decode())
            provided = qs.get("token", [""])[0]

        if not hmac.compare_digest(provided, self._api_key):
            response = JSONResponse(
                {"detail": "Invalid or missing API key"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
