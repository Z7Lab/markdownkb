"""HTTP transport scaffolding for the MCP server.

Hosts the utility-route ASGI middleware (``/logs``, ``/log-level``),
the allowed-hosts seed helper, and the ``run_http_with_auth`` entry
used by ``server.py`` when launched with ``--http``.
"""

import logging

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.logbuffer import log_buffer

logger = logging.getLogger(__name__)


class UtilityRoutesMiddleware:
    """ASGI wrapper intercepting ``/logs`` and ``/log-level``.

    Every other request (including lifespan) passes through untouched
    to the wrapped MCP app.
    """

    def __init__(self, inner):
        self._inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path == "/logs":
                await self._handle_logs(scope, receive, send)
                return
            if path == "/log-level":
                await self._handle_log_level(scope, receive, send)
                return
        await self._inner(scope, receive, send)

    async def _handle_logs(self, scope, receive, send):
        request = Request(scope, receive)
        if request.method == "DELETE":
            log_buffer.clear()
            response = JSONResponse({"status": "cleared"})
        else:
            since = int(request.query_params.get("since", 0))
            entries, seq = log_buffer.get_entries(since)
            response = JSONResponse({"entries": entries, "seq": seq})
        await response(scope, receive, send)

    async def _handle_log_level(self, scope, receive, send):
        request = Request(scope, receive)
        if request.method == "PUT":
            body = await request.json()
            level_str = body.get("level", "INFO").upper()
            level = 60 if level_str == "OFF" else getattr(logging, level_str, logging.INFO)
            logging.getLogger().setLevel(level)
            if level_str != "OFF":
                logger.info("MCP log level changed to %s", level_str)
            response = JSONResponse({"level": level_str})
        else:
            current = logging.getLogger().level
            level_name = "OFF" if current >= 60 else logging.getLevelName(current)
            response = JSONResponse({"level": level_name})
        await response(scope, receive, send)


def default_allowed_hosts(bind_host: str, port: int) -> list[str]:
    """Reachable-by-default hostnames to seed the Host allowlist.

    DNS rebinding protection rejects any Host header not on the allowlist,
    which is a common cause of "Invalid Host header" 400s from legitimate
    LAN or Docker-bridge clients. We seed the list with:
      - localhost / 127.0.0.1 (always)
      - host.docker.internal (common Docker-agent bridge name)
      - the machine's hostname and ``<hostname>.local`` (mDNS)
      - the machine's LAN IPs (best-effort via socket lookup)
      - the explicit bind host when it's a specific IP

    The user can tighten this by setting ``mcp.allowed_hosts`` in
    settings.yaml, or loosen it further with ``*``.  Each entry is expanded
    to both ``name:*`` (wildcard port) and ``name:<bind-port>`` so clients
    hitting either the default MCP port or a remapped one both work.
    """
    import socket

    names: list[str] = ["localhost", "127.0.0.1", "host.docker.internal"]
    try:
        hostname = socket.gethostname()
        if hostname:
            names.append(hostname)
            names.append(f"{hostname}.local")
    except OSError:
        pass
    try:
        _, _, lan_ips = socket.gethostbyname_ex(socket.gethostname())
        names.extend(lan_ips)
    except OSError:
        pass
    if bind_host not in ("0.0.0.0", "::", "127.0.0.1", "::1", "localhost"):
        names.append(bind_host)

    entries: list[str] = []
    seen: set[str] = set()
    for name in names:
        for pattern in (f"{name}:*", f"{name}:{port}"):
            if pattern not in seen:
                seen.add(pattern)
                entries.append(pattern)
    return entries


def run_http_with_auth(mcp: FastMCP, host: str, port: int):
    """Run Streamable HTTP transport with optional API key middleware.

    Middleware stack (outermost → innermost):
      CORSMiddleware        — adds CORS headers; handles OPTIONS preflight
      McpApiKeyMiddleware   — rejects requests without valid key (if configured)
      UtilityRoutesMiddleware — intercepts /logs and /log-level
      mcp_asgi              — FastMCP with DNS rebinding protection on /mcp

    CORS must be outermost so OPTIONS preflight responses are served without
    hitting auth middleware, which is standard browser CORS behaviour.
    """
    import anyio
    import uvicorn
    from starlette.middleware.cors import CORSMiddleware

    from app.config import Settings

    async def _serve():
        mcp.settings.host = host
        mcp.settings.port = port
        mcp_asgi = mcp.streamable_http_app()

        combined_app = UtilityRoutesMiddleware(mcp_asgi)

        settings = Settings.get()
        api_key = settings.api_key

        if api_key:
            from app.mcp.auth import McpApiKeyMiddleware
            combined_app = McpApiKeyMiddleware(combined_app, api_key)
            logger.info(
                "MCP auth enabled (accepts Authorization: Bearer or X-MarkdownKB-Key)"
            )
        else:
            logger.info("MCP auth disabled (no API key configured)")

        per_minute = settings.mcp_features.get("rate_limit_per_minute", 0) or 0
        try:
            per_minute = int(per_minute)
        except (TypeError, ValueError):
            per_minute = 0
        if per_minute > 0:
            from app.mcp.ratelimit import McpRateLimitMiddleware
            combined_app = McpRateLimitMiddleware(combined_app, per_minute=per_minute)
            logger.info("MCP rate limit enabled: %d requests per minute per key/IP", per_minute)
        else:
            logger.info("MCP rate limit disabled (mcp.rate_limit_per_minute is 0)")

        allowed_origins_setting = settings.mcp_features.get("allowed_origins", []) or []
        allowed_hosts_setting = settings.mcp_features.get("allowed_hosts", []) or []
        if "*" in allowed_origins_setting or "*" in allowed_hosts_setting:
            cors_origins = ["*"]
        elif allowed_origins_setting:
            cors_origins = [str(o) for o in allowed_origins_setting]
        else:
            # Default: restrict to localhost origins only (same conservative posture
            # as the main API).  Users can widen this via mcp.allowed_origins in
            # settings.yaml or by setting CORS_ORIGINS in the environment.
            cors_origins = [
                f"http://localhost:{port}",
                "http://localhost",
                "http://127.0.0.1",
                f"http://127.0.0.1:{port}",
            ]
        combined_app = CORSMiddleware(
            combined_app,
            allow_origins=cors_origins,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Accept", "Authorization", "X-MarkdownKB-Key"],
        )
        logger.info("MCP CORS enabled (origins: %s)", cors_origins)

        config = uvicorn.Config(
            combined_app, host=host, port=port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()

    anyio.run(_serve)
