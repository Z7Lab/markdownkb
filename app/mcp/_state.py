"""Shared module-level state for the MCP server.

Separated out so ``resources.py`` can read the cached resource dict set by
the lifespan in ``server.py`` without introducing an import cycle.
"""

cached_resources: dict | None = None
tools_registered: bool = False
