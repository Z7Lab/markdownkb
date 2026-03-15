"""MCP tool auto-discovery.

Each module in this package exports a ``TOOL`` dict and a ``handler``
function.  The discovery loop in ``mcp_server.py`` scans this package,
checks feature flags, and registers enabled tools on the FastMCP server.

TOOL dict keys:
    name:          str  — MCP tool name (must be unique)
    feature_flag:  str | None — key under ``mcp:`` in settings.yaml.
                   ``None`` means always enabled (core tool).
"""

import importlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def discover_tools(settings: Any) -> list[dict[str, Any]]:
    """Scan this package for tool modules and return enabled ones.

    Returns a list of dicts with keys ``name``, ``handler``, and
    ``enabled``.  Disabled tools are included with ``enabled=False``
    for logging purposes.
    """
    tools: list[dict[str, Any]] = []
    tools_dir = Path(__file__).resolve().parent

    for module_path in sorted(tools_dir.glob("*.py")):
        if module_path.name.startswith("_"):
            continue

        mod_name = module_path.stem
        try:
            mod = importlib.import_module(f"{__package__}.{mod_name}")
        except Exception:
            logger.exception("Failed to import MCP tool module '%s'", mod_name)
            continue

        meta = getattr(mod, "TOOL", None)
        handler = getattr(mod, "handler", None)
        if not meta or not handler or not callable(handler):
            continue

        flag = meta.get("feature_flag")
        enabled = True
        if flag and not settings.mcp_enabled(flag):
            enabled = False

        tools.append({
            "name": meta["name"],
            "handler": handler,
            "module": mod,
            "feature_flag": flag,
            "enabled": enabled,
        })

    return tools


def register_tools(mcp_server: Any, settings: Any) -> list[str]:
    """Discover and register enabled MCP tools on *mcp_server*.

    Returns the names of registered tools.
    """
    registered: list[str] = []

    for tool in discover_tools(settings):
        if not tool["enabled"]:
            logger.info(
                "MCP tool disabled: %s (mcp.%s: false)",
                tool["name"], tool["feature_flag"],
            )
            continue

        # Inject the FastMCP instance so tools can call get_context()
        tool["module"]._mcp = mcp_server

        mcp_server.tool(name=tool["name"])(tool["handler"])
        registered.append(tool["name"])
        logger.info("MCP tool registered: %s", tool["name"])

    return registered
