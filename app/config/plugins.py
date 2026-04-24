"""Plugin and service configuration mixin."""


class PluginsMixin:
    """CRUD for plugin and shared-service configuration blocks."""

    # --- Plugins ---

    def plugin_enabled(self, name: str) -> bool:
        """Check whether plugin *name* is enabled via ``plugins.<name>.enabled``."""
        cfg = self._data.get("plugins", {}).get(name)
        if not isinstance(cfg, dict):
            return bool(cfg) if cfg is not None else False
        return cfg.get("enabled", False)

    def set_plugin_enabled(self, name: str, enabled: bool) -> None:
        """Set ``plugins.<name>.enabled``."""
        self._data.setdefault("plugins", {}).setdefault(name, {})["enabled"] = enabled

    def get_plugin_config(self, plugin_name: str) -> dict:
        """Return the config dict for a plugin, excluding ``enabled``."""
        cfg = dict(self._data.get("plugins", {}).get(plugin_name, {}))
        cfg.pop("enabled", None)
        return cfg

    def set_plugin_config(self, plugin_name: str, config: dict) -> None:
        """Merge *config* into ``plugins.<name>`` (shallow update)."""
        plugins = self._data.setdefault("plugins", {})
        existing = plugins.setdefault(plugin_name, {})
        existing.update(config)

    def remove_plugin_config(self, plugin_name: str) -> None:
        """Remove a plugin's configuration section entirely."""
        self._data.get("plugins", {}).pop(plugin_name, None)

    # --- Services (shared infra like deep_research) ---

    def get_service_config(self, service_name: str) -> dict:
        """Return config for a shared service from ``services.<name>``."""
        return dict(self._data.get("services", {}).get(service_name, {}))

    def set_service_config(self, service_name: str, config: dict) -> None:
        """Merge *config* into ``services.<name>``."""
        services = self._data.setdefault("services", {})
        existing = services.setdefault(service_name, {})
        existing.update(config)
