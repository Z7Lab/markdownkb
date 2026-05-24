"""Legacy-layout migrations for ``settings.yaml``.

Extracted from ``app.config.__init__`` so the top-level Settings module
stays focused on the Settings class itself. These functions mutate the
``data`` dict in place and return True when a migration was applied so the
caller can persist the result.
"""

import logging

logger = logging.getLogger(__name__)


_CORE_FLAGS = frozenset({
    "file_watcher", "rate_limiting",
    "deep_research", "agent_skills",
    "update_check",
    # Preserved for migration backward compat — these flags have no active
    # gate in production code and are not present in the example config.
    "rag_chat", "diagnostics",
})

# Old feature-flag name → plugin directory name
_PLUGIN_FLAG_MAP = {
    "search": "search",
    "export": "export",
    "tags": "tags",
    "docmap": "docmap",
    "knowledge_graph": "knowledge_graph",
    "mcts_planner": "planner",
    "write_api": "write_api",
}


def migrate_settings(data: dict) -> bool:
    """Migrate legacy ``features:``/``plugins:`` layout to core/mcp/plugins/services.

    Applied to configs written before v0.4.0. Safe to remove once no pre-0.4.0
    configs remain in the wild (sentinel: ``"features" not in data``).
    Returns True if migration was performed (caller should save).
    """
    if "features" not in data or "core" in data:
        return False  # already migrated or fresh install

    old_features = data.pop("features")
    old_plugins = data.pop("plugins", {})

    core: dict[str, bool] = {}
    for flag in sorted(_CORE_FLAGS):
        if flag in old_features:
            core[flag] = old_features[flag]
    data["core"] = core

    plugins: dict[str, dict] = {}
    for old_flag, plugin_name in _PLUGIN_FLAG_MAP.items():
        cfg = dict(old_plugins.pop(plugin_name, {}))
        if old_flag in old_features:
            cfg["enabled"] = old_features[old_flag]
        plugins[plugin_name] = cfg
    if "mcp_tag_generator" in old_features:
        plugins.setdefault("tags", {})["ai_generation"] = old_features["mcp_tag_generator"]
    for name, cfg in old_plugins.items():
        if name == "deep_research":
            continue  # handled below as a service
        plugins.setdefault(name, {}).update(cfg)
    data["plugins"] = plugins

    services: dict[str, dict] = {}
    if "deep_research" in old_plugins:
        services["deep_research"] = dict(old_plugins["deep_research"])
    data["services"] = services

    logger.info("Migrated settings from legacy features: layout to core/mcp/plugins/services")
    return True


def migrate_num_ctx(data: dict) -> bool:
    """Move legacy top-level ``num_ctx`` into each provider's ``extra_body``.

    Applied to configs written before v0.5.0. Safe to remove once no pre-0.5.0
    configs remain in the wild (sentinel: ``"num_ctx" not in provider``).
    Returns True if any migration was performed.
    """
    migrated = False
    for provider in data.get("llm", {}).get("providers", []):
        if "num_ctx" in provider:
            provider.setdefault("extra_body", {})["num_ctx"] = provider.pop("num_ctx")
            migrated = True
    if migrated:
        logger.info("Migrated legacy provider num_ctx to extra_body.num_ctx")
    return migrated
