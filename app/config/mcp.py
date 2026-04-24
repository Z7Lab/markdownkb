"""MCP tool configuration mixin."""

import logging

import yaml

from app.config._paths import resolve_env_recursive as _resolve_env_recursive

logger = logging.getLogger(__name__)


class MCPMixin:
    """Mixin providing MCP tool configuration CRUD (load, save, get, set)."""

    def _load_mcp_config(self, tool_name: str) -> dict:
        """Load MCP tool config from tool folder + user overrides."""
        with self._lock:
            if tool_name in self._mcp_cache:
                return self._mcp_cache[tool_name]

            # Load default config from tool folder (app/mcp/{tool_name}/config.yaml)
            tool_dir = self._project_root / "app" / "mcp" / tool_name
            tool_config_file = tool_dir / "config.yaml"

            config = {}
            if tool_config_file.exists():
                try:
                    with open(tool_config_file, encoding="utf-8") as f:
                        config = yaml.safe_load(f) or {}
                except (OSError, yaml.YAMLError) as e:
                    logger.warning("Failed to load MCP config %s: %s", tool_config_file, e)

            # Overlay user overrides from config/mcp/{tool_name}.yaml
            user_config_file = self._mcp_dir / f"{tool_name}.yaml"
            if user_config_file.exists():
                try:
                    with open(user_config_file, encoding="utf-8") as f:
                        user_config = yaml.safe_load(f) or {}
                    config.update(user_config)
                except (OSError, yaml.YAMLError) as e:
                    logger.warning("Failed to load MCP user config %s: %s", user_config_file, e)

            config = _resolve_env_recursive(config)
            self._mcp_cache[tool_name] = config
            return config

    def _save_mcp_config(self, tool_name: str, config: dict):
        """Save MCP tool config to separate YAML file."""
        self._mcp_dir.mkdir(parents=True, exist_ok=True)
        config_file = self._mcp_dir / f"{tool_name}.yaml"

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(
                config, f,
                default_flow_style=False, sort_keys=False,
            )
        self._mcp_cache[tool_name] = config

    @property
    def mcp_config(self) -> dict:
        """Return all MCP tools configuration as a single dict."""
        # Discover MCP tools from app/mcp/ directories
        configs = {}
        mcp_tools_dir = self._project_root / "app" / "mcp"
        if mcp_tools_dir.exists():
            for tool_dir in mcp_tools_dir.iterdir():
                if tool_dir.is_dir() and (tool_dir / "config.yaml").exists():
                    tool_name = tool_dir.name
                    configs[tool_name] = self._load_mcp_config(tool_name)
        return configs

    def get_mcp_config(self, tool_name: str) -> dict:
        """Get configuration for a specific MCP tool from its YAML file."""
        return self._load_mcp_config(tool_name)

    def set_mcp_config(self, tool_name: str, config: dict):
        """Set configuration for a specific MCP tool and save to its YAML file."""
        with self._lock:
            self._save_mcp_config(tool_name, config)
