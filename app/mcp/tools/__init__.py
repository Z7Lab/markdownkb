"""MCP tool auto-discovery.

Each module in this package exports a ``TOOL`` dict and a ``handler``
function.  The discovery loop in ``mcp_server.py`` scans this package,
checks feature flags, and registers enabled tools on the FastMCP server.

TOOL dict keys:
    name:          str  — MCP tool name (must be unique)
    feature_flag:  str | None — key under ``mcp:`` in settings.yaml.
                   ``None`` means always enabled (core tool).
    requires_plugin: str | None — plugin name that must be enabled
                   (checked via ``settings.plugin_enabled(name)``).
    write:         bool — if True, this tool performs writes and is
                   disabled when ``mcp.read_only`` is enabled.
"""

import importlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def discover_tools(settings: Any) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Scan this package for tool modules and return enabled ones.

    Returns a tuple of (tools, import_errors).  ``tools`` is a list of
    dicts with keys ``name``, ``handler``, and ``enabled``.  Disabled
    tools are included with ``enabled=False`` for logging purposes.
    ``import_errors`` lists modules that failed to import.
    """
    tools: list[dict[str, Any]] = []
    import_errors: list[dict[str, str]] = []
    tools_dir = Path(__file__).resolve().parent

    for module_path in sorted(tools_dir.glob("*.py")):
        if module_path.name.startswith("_"):
            continue

        mod_name = module_path.stem
        try:
            mod = importlib.import_module(f"{__package__}.{mod_name}")
        except Exception as e:
            logger.exception("Failed to import MCP tool module '%s'", mod_name)
            import_errors.append({"module": mod_name, "error": str(e)})
            continue

        meta = getattr(mod, "TOOL", None)
        handler = getattr(mod, "handler", None)
        if not meta or not handler or not callable(handler):
            continue

        flag = meta.get("feature_flag")
        requires_plugin = meta.get("requires_plugin")
        is_write = meta.get("write", False)
        enabled = True
        if flag and not settings.mcp_enabled(flag):
            enabled = False
        if requires_plugin and not settings.plugin_enabled(requires_plugin):
            enabled = False
        if is_write and settings.mcp_enabled("read_only"):
            enabled = False

        tools.append({
            "name": meta["name"],
            "handler": handler,
            "module": mod,
            "feature_flag": flag,
            "requires_plugin": requires_plugin,
            "write": is_write,
            "enabled": enabled,
        })

    return tools, import_errors


def register_tools(mcp_server: Any, settings: Any) -> list[str]:
    """Discover and register enabled MCP tools on *mcp_server*.

    Returns the names of registered tools.
    """
    registered: list[str] = []

    tools, import_errors = discover_tools(settings)
    for error in import_errors:
        logger.warning(
            "MCP tool module '%s' failed to import: %s",
            error["module"], error["error"],
        )

    for tool in tools:
        if not tool["enabled"]:
            if tool.get("requires_plugin") and not settings.plugin_enabled(tool["requires_plugin"]):
                reason = f"plugin '{tool['requires_plugin']}' disabled"
            elif tool.get("write") and settings.mcp_enabled("read_only"):
                reason = "mcp.read_only: true"
            else:
                reason = f"mcp.{tool['feature_flag']}: false"
            logger.info("MCP tool disabled: %s (%s)", tool["name"], reason)
            continue

        # Inject the FastMCP instance so tools can call get_context()
        tool["module"]._mcp = mcp_server

        mcp_server.tool(name=tool["name"])(tool["handler"])
        registered.append(tool["name"])
        logger.info("MCP tool registered: %s", tool["name"])

    return registered
