"""MCP tool configuration mixin."""

import logging

import yaml

from app.config._paths import resolve_env_recursive as _resolve_env_recursive

logger = logging.getLogger(__name__)


class MCPMixin:
    """Mixin providing MCP tool configuration CRUD (load, save, get, set).

    Built-in defaults live in ``app/mcp/{tool_name}/config.yaml`` (shipped
    with the code, never written at runtime).  User overrides are stored
    under the ``mcp_configs`` key in the settings database so they survive
    container restarts without requiring a writable config directory.
    """

    def _load_mcp_config(self, tool_name: str) -> dict:
        """Load MCP tool config: built-in defaults overlaid with DB overrides."""
        with self._lock:
            if tool_name in self._mcp_cache:
                return self._mcp_cache[tool_name]

            # Built-in defaults from the tool's own config.yaml (read-only, part of the image).
            tool_dir = self._project_root / "app" / "mcp" / tool_name
            tool_config_file = tool_dir / "config.yaml"

            config = {}
            if tool_config_file.exists():
                try:
                    with open(tool_config_file, encoding="utf-8") as f:
                        config = yaml.safe_load(f) or {}
                except (OSError, yaml.YAMLError) as e:
                    logger.warning("Failed to load MCP config %s: %s", tool_config_file, e)

            # User overrides from the settings database.
            user_overrides = self._data.get("mcp_configs", {}).get(tool_name, {})
            if user_overrides:
                config.update(user_overrides)

            config = _resolve_env_recursive(config)
            self._mcp_cache[tool_name] = config
            return config

    def _save_mcp_config(self, tool_name: str, config: dict) -> None:
        """Persist user overrides for an MCP tool to the settings database."""
        self._data.setdefault("mcp_configs", {})[tool_name] = config
        self._mcp_cache[tool_name] = config

    @property
    def mcp_config(self) -> dict:
        """Return all MCP tools configuration as a single dict."""
        configs = {}
        mcp_tools_dir = self._project_root / "app" / "mcp"
        if mcp_tools_dir.exists():
            for tool_dir in mcp_tools_dir.iterdir():
                if tool_dir.is_dir() and (tool_dir / "config.yaml").exists():
                    tool_name = tool_dir.name
                    configs[tool_name] = self._load_mcp_config(tool_name)
        return configs

    def get_mcp_config(self, tool_name: str) -> dict:
        """Get configuration for a specific MCP tool."""
        return self._load_mcp_config(tool_name)

    def set_mcp_config(self, tool_name: str, config: dict) -> None:
        """Set configuration for a specific MCP tool (caller must call save())."""
        with self._lock:
            self._save_mcp_config(tool_name, config)
