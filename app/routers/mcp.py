"""MCP inspection and configuration endpoints.

Drives the Settings > MCP panel — exposes connection info, the tool
browser (auto-discovered from app/mcp/tools/), and the allowed_hosts
editor.  Feature flag toggles live in ``app/routers/settings.py``
(``PUT /api/v1/settings/mcp-flags``).
"""

import inspect
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_settings
from app.mcp.tools import discover_tools
from app.ratelimit import STANDARD, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])

# Shared client — reuses TCP connections across log-proxy calls instead of
# opening a new connection per request (which causes FD exhaustion under polling).
_mcp_http_client = httpx.AsyncClient(timeout=5.0)


_PARAM_TYPE_NAMES: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _type_name(annotation: Any) -> str:
    """Best-effort human-readable name for a tool parameter annotation."""
    if annotation is inspect.Parameter.empty or annotation is None:
        return "any"
    if annotation in _PARAM_TYPE_NAMES:
        return _PARAM_TYPE_NAMES[annotation]
    origin = getattr(annotation, "__origin__", None)
    if origin is list:
        return "array"
    if origin is dict:
        return "object"
    # Union / Optional — strip NoneType and recurse
    if getattr(annotation, "__args__", None):
        args = [a for a in annotation.__args__ if a is not type(None)]
        if len(args) == 1:
            return _type_name(args[0])
        return " | ".join(_type_name(a) for a in args) or "any"
    return getattr(annotation, "__name__", str(annotation))


def _handler_signature(handler: Any) -> list[dict[str, Any]]:
    """Introspect a tool handler and return its parameter metadata."""
    try:
        sig = inspect.signature(handler)
    except (TypeError, ValueError):
        return []
    params: list[dict[str, Any]] = []
    for name, p in sig.parameters.items():
        params.append({
            "name": name,
            "type": _type_name(p.annotation),
            "required": p.default is inspect.Parameter.empty,
            "default": None if p.default is inspect.Parameter.empty else repr(p.default),
        })
    return params


def _mcp_endpoint_url(request: Request) -> str:
    """Best-effort MCP endpoint URL for display in the settings panel.

    The MCP server is a separate process — its host/port come from CLI
    flags, not the settings.yaml.  We expose env var overrides so users
    running non-default deployments see the right URL, and fall back to
    the host the user is currently hitting + default port 9715.
    """
    explicit = os.environ.get("MARKDOWNKB_MCP_URL")
    if explicit:
        return explicit
    host = os.environ.get("MARKDOWNKB_MCP_HOST")
    port = os.environ.get("MARKDOWNKB_MCP_PORT", "9715")
    if not host:
        # Use the hostname the browser is currently talking to so the
        # displayed URL "just works" from the same machine.
        host = request.url.hostname or "localhost"
    return f"http://{host}:{port}/mcp"


@router.get("/info")
@limiter.limit(STANDARD)
def get_mcp_info(request: Request, settings: Settings = Depends(get_settings)):
    """Return MCP connection info, feature flags, and allowed_hosts.

    Drives the top of the Settings > MCP panel.  The endpoint URL is a
    display hint — the MCP server runs in its own process and may be
    behind a proxy.
    """
    endpoint = _mcp_endpoint_url(request)
    mcp_features = settings.mcp_features
    auth_enabled = bool(getattr(request.app.state, "api_key", ""))

    # Split the mcp section into flags (bool) and other settings
    flags = {
        k: bool(v)
        for k, v in mcp_features.items()
        if isinstance(v, bool)
    }
    allowed_hosts = mcp_features.get("allowed_hosts", []) or []
    if not isinstance(allowed_hosts, list):
        allowed_hosts = []
    allowed_origins = mcp_features.get("allowed_origins", []) or []
    if not isinstance(allowed_origins, list):
        allowed_origins = []

    rate_limit_per_minute = mcp_features.get("rate_limit_per_minute", 0) or 0
    try:
        rate_limit_per_minute = int(rate_limit_per_minute)
    except (TypeError, ValueError):
        rate_limit_per_minute = 0

    return {
        "endpoint": endpoint,
        "transport": "streamable_http",
        "auth_enabled": auth_enabled,
        "auth_methods": (
            ["Bearer token", "X-MarkdownKB-Key header"]
            if auth_enabled else []
        ),
        "flags": flags,
        "allowed_hosts": [str(h) for h in allowed_hosts],
        "allowed_origins": [str(o) for o in allowed_origins],
        "rate_limit_per_minute": rate_limit_per_minute,
    }


@router.get("/tools")
@limiter.limit(STANDARD)
def list_mcp_tools(request: Request, settings: Settings = Depends(get_settings)):
    """Return every discovered MCP tool with metadata and enabled state.

    Powers the Settings > MCP tool browser.  Tools whose feature flag or
    required plugin is disabled are included with ``enabled: false`` and
    a ``disabled_reason`` so users can see what they'd get by flipping a
    flag.
    """
    tools, import_errors = discover_tools(settings)

    items: list[dict[str, Any]] = []
    for t in tools:
        handler = t["handler"]
        doc = (inspect.getdoc(handler) or "").strip()
        # Short description = first paragraph only
        description = doc.split("\n\n", 1)[0] if doc else ""

        disabled_reason: str | None = None
        if not t["enabled"]:
            if t.get("requires_plugin") and not settings.plugin_enabled(t["requires_plugin"]):
                disabled_reason = f"plugin '{t['requires_plugin']}' disabled"
            elif t.get("write") and settings.mcp_enabled("read_only"):
                disabled_reason = "mcp.read_only is true"
            elif t.get("feature_flag"):
                disabled_reason = f"mcp.{t['feature_flag']} is false"

        items.append({
            "name": t["name"],
            "description": description,
            "write": bool(t.get("write")),
            "requires_plugin": t.get("requires_plugin"),
            "feature_flag": t.get("feature_flag"),
            "enabled": bool(t["enabled"]),
            "disabled_reason": disabled_reason,
            "parameters": _handler_signature(handler),
        })

    items.sort(key=lambda i: i["name"])
    enabled_count = sum(1 for i in items if i["enabled"])

    return {
        "tools": items,
        "total": len(items),
        "enabled": enabled_count,
        "import_errors": import_errors,
    }


class AllowedHostsRequest(BaseModel):
    """Request model for updating MCP allowed_hosts."""

    allowed_hosts: list[str] = Field(default_factory=list)


@router.put("/allowed-hosts")
@limiter.limit(STANDARD)
def update_allowed_hosts(
    request: Request,
    req: AllowedHostsRequest,
    settings: Settings = Depends(get_settings),
):
    """Replace the ``mcp.allowed_hosts`` list.

    Used for DNS rebinding protection on the Streamable HTTP transport.
    Takes effect after the MCP server is restarted.
    """
    cleaned = [h.strip() for h in req.allowed_hosts if h and h.strip()]
    settings.set_mcp_allowed_hosts(cleaned)
    settings.save()
    return {"status": "saved", "allowed_hosts": cleaned}


class AllowedOriginsRequest(BaseModel):
    """Request model for updating MCP allowed_origins."""

    allowed_origins: list[str] = Field(default_factory=list)


@router.put("/allowed-origins")
@limiter.limit(STANDARD)
def update_allowed_origins(
    request: Request,
    req: AllowedOriginsRequest,
    settings: Settings = Depends(get_settings),
):
    """Replace the ``mcp.allowed_origins`` list.

    Used to control which client origins (browser Origin headers) are allowed.
    Use ``*`` to allow all origins, or ``http://hostname:*`` for wildcard port
    matching.  Takes effect after the MCP server is restarted.
    """
    cleaned = [o.strip() for o in req.allowed_origins if o and o.strip()]
    settings.set_mcp_allowed_origins(cleaned)
    settings.save()
    return {"status": "saved", "allowed_origins": cleaned}


class RateLimitRequest(BaseModel):
    """Request model for updating the MCP per-key rate cap."""

    per_minute: int = Field(0, ge=0, le=100000)


@router.put("/rate-limit")
@limiter.limit(STANDARD)
def update_rate_limit(
    request: Request,
    req: RateLimitRequest,
    settings: Settings = Depends(get_settings),
):
    """Set the MCP rate cap (requests per minute per API key / IP).

    0 disables rate limiting. Takes effect after the MCP server restarts.
    """
    settings.set_mcp_rate_limit(req.per_minute)
    settings.save()
    return {"status": "saved", "rate_limit_per_minute": req.per_minute}


# -- MCP server log proxy -------------------------------------------------------
# The MCP server runs in a separate process (and Docker container).
# These endpoints proxy to its /logs and /log-level routes so the frontend
# can read MCP logs without making cross-origin requests.

def _mcp_internal_base() -> str:
    """Internal base URL for the MCP server (Docker service or localhost)."""
    return os.environ.get("MARKDOWNKB_MCP_INTERNAL_URL", "http://localhost:9715")


async def _mcp_get(path: str, settings: Settings, params: dict | None = None):
    headers = {"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {}
    try:
        resp = await _mcp_http_client.get(
            f"{_mcp_internal_base()}{path}", headers=headers, params=params,
        )
        return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(503, f"MCP server unavailable: {exc}") from exc


async def _mcp_delete(path: str, settings: Settings):
    headers = {"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {}
    try:
        resp = await _mcp_http_client.delete(
            f"{_mcp_internal_base()}{path}", headers=headers,
        )
        return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(503, f"MCP server unavailable: {exc}") from exc


async def _mcp_put(path: str, body: dict, settings: Settings):
    headers = {"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {}
    try:
        resp = await _mcp_http_client.put(
            f"{_mcp_internal_base()}{path}", json=body, headers=headers,
        )
        return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(503, f"MCP server unavailable: {exc}") from exc


@router.get("/logs")
@limiter.limit(STANDARD)
async def get_mcp_logs(
    request: Request, since: int = 0, settings: Settings = Depends(get_settings),
):
    """Proxy GET /logs from the MCP server's ring buffer."""
    return await _mcp_get("/logs", settings, params={"since": since})


@router.delete("/logs")
@limiter.limit(STANDARD)
async def clear_mcp_logs(request: Request, settings: Settings = Depends(get_settings)):
    """Proxy DELETE /logs to clear the MCP server's ring buffer."""
    return await _mcp_delete("/logs", settings)


class McpLogLevelRequest(BaseModel):
    level: str = Field(default="INFO")


@router.get("/log-level")
@limiter.limit(STANDARD)
async def get_mcp_log_level(request: Request, settings: Settings = Depends(get_settings)):
    """Proxy GET /log-level from the MCP server."""
    return await _mcp_get("/log-level", settings)


@router.put("/log-level")
@limiter.limit(STANDARD)
async def set_mcp_log_level(
    request: Request,
    req: McpLogLevelRequest,
    settings: Settings = Depends(get_settings),
):
    """Proxy PUT /log-level to change the MCP server's log level at runtime."""
    return await _mcp_put("/log-level", {"level": req.level}, settings)
