"""Rate limiting middleware for the MCP server.

Sliding-window-counter limiter keyed by API key (when configured) or the
client's remote address (when not).  In-memory, per-process — adequate for
a single-instance MCP deployment.  Counters are pruned on the fly.

Off by default.  Enable by setting ``mcp.rate_limit_per_minute`` in
``config/settings.yaml`` to a positive integer, or via Settings → MCP in
the web UI.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from threading import Lock

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 60.0
_HEADER = "X-MarkdownKB-Key"
_BEARER_PREFIX = "Bearer "


class McpRateLimitMiddleware:
    """ASGI middleware enforcing a per-key request-rate cap.

    Excludes utility endpoints (/logs, /log-level) so debugging the
    rate-limit itself doesn't trip the limit.
    """

    EXEMPT_PATHS = frozenset({"/logs", "/log-level"})

    def __init__(self, app: ASGIApp, per_minute: int):
        self.app = app
        self.per_minute = max(1, int(per_minute))
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._counts: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in self.EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        key = self._key_for(scope)
        now = time.monotonic()
        retry_after = self._consume(key, now)
        if retry_after is not None:
            self._counts[key] += 1
            response = JSONResponse(
                {
                    "detail": "Rate limit exceeded",
                    "limit_per_minute": self.per_minute,
                },
                status_code=429,
                headers={"Retry-After": str(int(retry_after) + 1)},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def _consume(self, key: str, now: float) -> float | None:
        """Try to consume one request slot.  Returns seconds-to-wait if denied."""
        with self._lock:
            window = self._buckets[key]
            cutoff = now - _WINDOW_SECONDS
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= self.per_minute:
                return _WINDOW_SECONDS - (now - window[0])
            window.append(now)
            self._counts[key] += 1
        return None

    def _key_for(self, scope: Scope) -> str:
        """Identify the client by API key (preferred) or remote address."""
        request = Request(scope)
        auth = request.headers.get("Authorization", "")
        if auth.startswith(_BEARER_PREFIX):
            return f"key:{auth[len(_BEARER_PREFIX):]}"
        header_key = request.headers.get(_HEADER, "")
        if header_key:
            return f"key:{header_key}"
        client = scope.get("client")
        if client and len(client) >= 1:
            return f"ip:{client[0]}"
        return "ip:unknown"

    def usage_snapshot(self) -> dict[str, dict]:
        """Return a compact view of recent usage per key (for an admin endpoint)."""
        with self._lock:
            now = time.monotonic()
            cutoff = now - _WINDOW_SECONDS
            out: dict[str, dict] = {}
            for key, window in self._buckets.items():
                while window and window[0] < cutoff:
                    window.popleft()
                out[key] = {
                    "current_window": len(window),
                    "limit_per_minute": self.per_minute,
                    "lifetime_requests": self._counts[key],
                }
        return out
