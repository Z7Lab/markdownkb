"""Tests for settings migration from legacy features: layout to new structure."""

from pathlib import Path

import yaml

from app.config import Settings, _migrate_settings


def _write_yaml(tmp_path: Path, data: dict) -> Path:
    config_file = tmp_path / "config" / "settings.yaml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text(yaml.dump(data, default_flow_style=False))
    # Prompts dir required by Settings
    prompts_dir = config_file.parent / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (prompts_dir / "system.md").write_text("You are helpful.")
    return config_file


def test_migration_from_old_format(tmp_path):
    """Old YAML with features: section migrates to core/mcp/plugins/services."""
    old_config = {
        "features": {
            "rag_chat": True,
            "file_watcher": True,
            "rate_limiting": False,
            "deep_research": False,
            "agent_skills": False,
            "diagnostics": False,
            "search": True,
            "export": True,
            "tags": True,
            "knowledge_graph": True,
            "mcts_planner": True,
            "write_api": False,
            "mcp_tag_generator": False,
        },
        "plugins": {
            "search": {"chunk_multiplier": 10},
            "deep_research": {"iterations": 5, "n_approaches": 4},
        },
    }
    config_file = _write_yaml(tmp_path, old_config)
    s = Settings(config_file)

    # features: section should be gone from raw data
    assert "features" not in s._data

    # core flags
    assert s._data["core"]["rag_chat"] is True
    assert s._data["core"]["deep_research"] is False
    assert s._data["core"]["rate_limiting"] is False

    # mcp section exists (may be empty — filesystem/terminal were removed)
    assert "mcp" in s._data

    # plugin enabled + config merged
    assert s._data["plugins"]["search"]["enabled"] is True
    assert s._data["plugins"]["search"]["chunk_multiplier"] == 10
    assert s._data["plugins"]["knowledge_graph"]["enabled"] is True
    assert s._data["plugins"]["planner"]["enabled"] is True
    assert s._data["plugins"]["write_api"]["enabled"] is False
    assert s._data["plugins"]["tags"]["ai_generation"] is False

    # deep_research config moved to services
    assert s._data["services"]["deep_research"]["iterations"] == 5
    assert s._data["services"]["deep_research"]["n_approaches"] == 4


def test_migration_preserves_plugin_config(tmp_path):
    """Existing plugin config survives migration and merges with enabled flag."""
    old_config = {
        "features": {"search": True},
        "plugins": {
            "search": {"chunk_multiplier": 15, "exact_phrase_matching": True},
        },
    }
    config_file = _write_yaml(tmp_path, old_config)
    s = Settings(config_file)

    cfg = s.get_plugin_config("search")
    assert cfg["chunk_multiplier"] == 15
    assert cfg["exact_phrase_matching"] is True
    assert "enabled" not in cfg  # filtered out


def test_migration_idempotent(tmp_path):
    """Already-migrated YAML is not modified."""
    new_config = {
        "core": {"rag_chat": True},
        "mcp": {"filesystem": False},
        "plugins": {"search": {"enabled": True, "chunk_multiplier": 10}},
        "services": {},
    }
    data = dict(new_config)
    assert _migrate_settings(data) is False
    assert data == new_config


def test_migrated_flags_accessible_via_direct_methods(tmp_path):
    """After migration, flags are accessible via core_enabled/mcp_enabled/plugin_enabled."""
    old_config = {
        "features": {
            "rag_chat": True,
            "knowledge_graph": True,
            "mcp_tag_generator": True,
        },
    }
    config_file = _write_yaml(tmp_path, old_config)
    s = Settings(config_file)

    assert s.core_enabled("rag_chat") is True
    assert s.plugin_enabled("knowledge_graph") is True
    assert s.get_plugin_config("tags").get("ai_generation") is True


def test_plugin_config_excludes_enabled(tmp_path):
    """get_plugin_config filters out the 'enabled' key."""
    new_config = {
        "core": {},
        "mcp": {},
        "plugins": {"search": {"enabled": True, "chunk_multiplier": 10}},
        "services": {},
    }
    config_file = _write_yaml(tmp_path, new_config)
    s = Settings(config_file)

    cfg = s.get_plugin_config("search")
    assert "enabled" not in cfg
    assert cfg["chunk_multiplier"] == 10


def test_direct_setters(tmp_path):
    """set_core/set_mcp_enabled/set_plugin_enabled write to correct sections."""
    new_config = {
        "core": {"rag_chat": True},
        "mcp": {"filesystem": False},
        "plugins": {"search": {"enabled": True}},
        "services": {},
    }
    config_file = _write_yaml(tmp_path, new_config)
    s = Settings(config_file)

    # Core flag
    s.set_core("rag_chat", False)
    assert s._data["core"]["rag_chat"] is False

    # MCP flag
    s.set_mcp_enabled("filesystem", True)
    assert s._data["mcp"]["filesystem"] is True

    # Plugin flag
    s.set_plugin_enabled("graph", True)
    assert s._data["plugins"]["graph"]["enabled"] is True


def test_plugin_enabled(tmp_path):
    """plugin_enabled reads from plugins.<name>.enabled."""
    new_config = {
        "core": {},
        "mcp": {},
        "plugins": {
            "search": {"enabled": True},
            "export": {"enabled": False},
        },
        "services": {},
    }
    config_file = _write_yaml(tmp_path, new_config)
    s = Settings(config_file)

    assert s.plugin_enabled("search") is True
    assert s.plugin_enabled("export") is False
    assert s.plugin_enabled("nonexistent") is False


def test_set_plugin_enabled(tmp_path):
    """set_plugin_enabled writes to plugins.<name>.enabled."""
    new_config = {
        "core": {},
        "mcp": {},
        "plugins": {},
        "services": {},
    }
    config_file = _write_yaml(tmp_path, new_config)
    s = Settings(config_file)

    s.set_plugin_enabled("my_plugin", True)
    assert s._data["plugins"]["my_plugin"]["enabled"] is True
    assert s.plugin_enabled("my_plugin") is True


def test_service_config(tmp_path):
    """get/set_service_config works for shared services."""
    new_config = {
        "core": {},
        "mcp": {},
        "plugins": {},
        "services": {"deep_research": {"iterations": 5}},
    }
    config_file = _write_yaml(tmp_path, new_config)
    s = Settings(config_file)

    cfg = s.get_service_config("deep_research")
    assert cfg["iterations"] == 5

    s.set_service_config("deep_research", {"n_approaches": 4})
    cfg = s.get_service_config("deep_research")
    assert cfg["iterations"] == 5
    assert cfg["n_approaches"] == 4


def test_migration_persisted_to_db(tmp_path):
    """Migration saves the new format to the settings database (not back to YAML)."""
    from app.config.settingsdb import SettingsDB

    old_config = {
        "features": {"rag_chat": True, "search": True},
        "plugins": {"search": {"chunk_multiplier": 10}},
    }
    config_file = _write_yaml(tmp_path, old_config)
    Settings(config_file)

    # Migration output is in the DB, not rewritten to the YAML file.
    db = SettingsDB(config_file.parent)
    persisted = db.load()
    assert persisted is not None
    assert "features" not in persisted
    assert "core" in persisted
    assert persisted["plugins"]["search"]["enabled"] is True
    assert persisted["plugins"]["search"]["chunk_multiplier"] == 10
