"""Tests for the Settings config class."""

import pytest
import yaml


@pytest.fixture
def config_dir(tmp_path):
    """Create a temp config directory with a settings.yaml (new format)."""
    config = {
        "sources": [{"path": "/tmp/docs", "writable": True}],
        "core": {"rag_chat": True},
        "mcp": {},
        "plugins": {
            "search": {"enabled": False, "top_k": 10},
        },
        "services": {},
    }
    config_file = tmp_path / "config" / "settings.yaml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text(yaml.dump(config))
    # Create prompts dir
    prompts_dir = tmp_path / "config" / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system.md").write_text("You are helpful.")
    return config_file


def test_settings_load(config_dir):
    from app.config import Settings
    s = Settings(config_dir)
    assert s.sources == ["/tmp/docs"]


def test_core_enabled(config_dir):
    from app.config import Settings
    s = Settings(config_dir)
    assert s.core_enabled("rag_chat") is True
    assert s.core_enabled("nonexistent") is False


def test_set_core(config_dir):
    from app.config import Settings
    s = Settings(config_dir)
    s.set_core("rag_chat", False)
    assert s.core_enabled("rag_chat") is False
    s.set_core("rag_chat", True)
    assert s.core_enabled("rag_chat") is True


def test_plugin_config(config_dir):
    from app.config import Settings
    s = Settings(config_dir)
    cfg = s.get_plugin_config("search")
    assert cfg["top_k"] == 10
    assert "enabled" not in cfg  # filtered out
    s.set_plugin_config("search", {"top_k": 20})
    assert s.get_plugin_config("search")["top_k"] == 20


def test_prompt_cache_is_instance_level(config_dir):
    from app.config import Settings
    s1 = Settings(config_dir)
    s2 = Settings(config_dir)
    s1.get_prompt("system")
    # s2 should have its own empty cache
    assert "system" not in s2._prompt_cache


def test_prompt_reload(config_dir):
    from app.config import Settings
    s = Settings(config_dir)
    text = s.get_prompt("system")
    assert text == "You are helpful."
    s.reload_prompts()
    assert s._prompt_cache == {}
