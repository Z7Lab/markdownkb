"""Application configuration loaded from settings.yaml.

The Settings class is composed from domain-specific mixins:
- SourcesMixin: source directories, project roots, ignore patterns
- LLMMixin: LLM providers, active_provider, temperature, key resolution
- RetrievalMixin: top_k, thresholds, hybrid search, BM25
- PromptsMixin: prompt template loading, caching, overrides
- MCPMixin: MCP tool configuration CRUD

Settings layout (post-migration)::

    core:        # behaviour toggles that aren't plugins
    mcp:         # MCP tool enable flags (filesystem, terminal)
    plugins:     # each plugin: enabled + its config together
      search:
        enabled: true
        chunk_multiplier: 10
    services:    # shared service config (deep_research, etc.)

Legacy ``features:`` / flat ``plugins:`` layouts are auto-migrated on
first load and persisted back to disk.
"""

import logging
import os
import threading
from pathlib import Path
from typing import Any

import yaml

from app.config.llm import LLMMixin
from app.config.mcp import MCPMixin
from app.config.prompts import PromptsMixin
from app.config.retrieval import RetrievalMixin
from app.config.sources import SourcesMixin

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Settings migration: old flat ``features:`` → new structured layout
# ---------------------------------------------------------------------------

_CORE_FLAGS = frozenset({
    "rag_chat", "file_watcher", "rate_limiting",
    "deep_research", "agent_skills", "diagnostics",
})

_MCP_FLAGS = {
    "mcp_filesystem": "filesystem",
    "mcp_terminal": "terminal",
}

# Old feature-flag name → plugin directory name
_PLUGIN_FLAG_MAP = {
    "search": "search",
    "export": "export",
    "tags": "tags",
    "knowledge_graph": "graph",
    "mcts_planner": "planner",
    "write_api": "write_api",
}

def _migrate_settings(data: dict) -> bool:
    """Migrate legacy ``features:``/``plugins:`` layout to the new structure.

    Returns True if migration was performed (caller should save).
    """
    if "features" not in data or "core" in data:
        return False  # already migrated or fresh install

    old_features = data.pop("features")
    old_plugins = data.pop("plugins", {})

    # --- core ---
    core: dict[str, bool] = {}
    for flag in sorted(_CORE_FLAGS):
        if flag in old_features:
            core[flag] = old_features[flag]
    data["core"] = core

    # --- mcp ---
    mcp: dict[str, bool] = {}
    for old_key, new_key in _MCP_FLAGS.items():
        if old_key in old_features:
            mcp[new_key] = old_features[old_key]
    data["mcp"] = mcp

    # --- plugins (merge enabled flag into existing plugin config) ---
    plugins: dict[str, dict] = {}
    for old_flag, plugin_name in _PLUGIN_FLAG_MAP.items():
        cfg = dict(old_plugins.pop(plugin_name, {}))
        if old_flag in old_features:
            cfg["enabled"] = old_features[old_flag]
        plugins[plugin_name] = cfg
    # Handle mcp_tag_generator → plugins.tags.ai_generation
    if "mcp_tag_generator" in old_features:
        plugins.setdefault("tags", {})["ai_generation"] = old_features["mcp_tag_generator"]
    # Carry over any remaining old plugin configs (external plugins, etc.)
    for name, cfg in old_plugins.items():
        if name == "deep_research":
            continue  # handled below as a service
        plugins.setdefault(name, {}).update(cfg)
    data["plugins"] = plugins

    # --- services (deep_research config) ---
    services: dict[str, dict] = {}
    if "deep_research" in old_plugins:
        services["deep_research"] = dict(old_plugins["deep_research"])
    data["services"] = services

    logger.info("Migrated settings from legacy features: layout to core/mcp/plugins/services")
    return True

_DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "settings.yaml"
)


_SECRETS_DIR = Path(os.environ.get("MDKB_SECRETS_DIR", "/run/secrets"))
_DATA_SECRETS_DIR = Path("/app/data/secrets")


def _read_secret(name: str) -> str:
    """Read a secret by name.

    Checks data/secrets/ (writable, for generated keys) first, then
    Docker's read-only secrets mount (/run/secrets/).  Returns the
    file content (stripped) or empty string if not found or empty.
    """
    for directory in (_DATA_SECRETS_DIR, _SECRETS_DIR):
        path = directory / name
        try:
            if path.is_file():
                value = path.read_text().strip()
                if value:
                    return value
        except OSError as e:
            logger.warning("Failed to read secret '%s' from %s: %s", name, directory, e)
    return ""


def _resolve_env(value: str) -> str:
    """Replace ${VAR} placeholders with environment variable values."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        resolved = os.environ.get(env_var)
        if resolved is None:
            logger.warning(
                "Environment variable %s is not set (referenced in settings.yaml) — "
                "using empty string, which may disable dependent features",
                env_var,
            )
            return ""
        return resolved
    return value


def _resolve_env_recursive(obj: Any) -> Any:
    """Recursively resolve environment variable placeholders."""
    if isinstance(obj, str):
        return _resolve_env(obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_recursive(v) for v in obj]
    return obj


class Settings(SourcesMixin, LLMMixin, RetrievalMixin, PromptsMixin, MCPMixin):
    """Singleton settings manager backed by YAML config file."""

    _instance: "Settings | None" = None
    _class_lock = threading.Lock()

    def __init__(self, config_path: str | Path | None = None):
        path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        if path.exists():
            with open(path, encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
            self._using_defaults = False
        else:
            logger.warning("Config file not found at %s — using built-in defaults", path)
            self._data = {}
            self._using_defaults = True
        self._data = _resolve_env_recursive(self._data)
        self._path = path
        self._project_root = path.resolve().parent.parent
        self._lock = threading.Lock()
        self._mcp_cache: dict[str, dict] = {}
        self._prompt_cache: dict[str, str] = {}
        self._mcp_dir = self._path.parent / "mcp"

        # Auto-migrate legacy settings layout
        if _migrate_settings(self._data):
            self.save()

    @property
    def using_defaults(self) -> bool:
        """Return True if no config file was found and built-in defaults are in use."""
        return self._using_defaults

    @classmethod
    def get(cls, config_path: str | Path | None = None) -> "Settings":
        """Return the singleton instance, creating it if needed."""
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = cls(config_path)
            return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton for testing or reconfiguration."""
        with cls._class_lock:
            cls._instance = None

    def reload(self):
        """Re-read settings.yaml from disk and update the live instance.

        Preserves the singleton identity — all existing references to this
        object see the updated values immediately.
        """
        with self._lock:
            if self._path.exists():
                with open(self._path, encoding="utf-8") as f:
                    self._data = yaml.safe_load(f) or {}
                self._using_defaults = False
            else:
                self._data = {}
                self._using_defaults = True
            self._data = _resolve_env_recursive(self._data)
            self._mcp_cache.clear()
            self._prompt_cache.clear()
            logger.info("Settings reloaded from %s", self._path)

    def save(self):
        """Write current configuration back to the YAML file."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                yaml.dump(
                    self._data, f,
                    default_flow_style=False, sort_keys=False,
                )

    def _resolve_path(self, p: str) -> str:
        """Resolve a relative path against the project root."""
        path = Path(p)
        if not path.is_absolute():
            path = self._project_root / path
        return str(path.resolve())

    # --- Embeddings ---
    @property
    def embedding_model(self) -> str:
        """Return the configured embedding model name."""
        return self._data.get("embeddings", {}).get(
            "model", "all-MiniLM-L6-v2"
        )

    @embedding_model.setter
    def embedding_model(self, value: str):
        """Set the embedding model name."""
        self._data.setdefault("embeddings", {})["model"] = value

    # Fallback model definitions used when settings.yaml has no models list
    _DEFAULT_MODELS = [
        {
            "model_id": "all-MiniLM-L6-v2",
            "display_name": "MiniLM L6 v2",
            "huggingface_repo": "sentence-transformers/all-MiniLM-L6-v2",
            "dimensions": 384,
            "max_seq_length": 256,
            "description": "Fast, lightweight (23MB). Good general purpose.",
        },
        {
            "model_id": "all-MiniLM-L12-v2",
            "display_name": "MiniLM L12 v2",
            "huggingface_repo": "sentence-transformers/all-MiniLM-L12-v2",
            "dimensions": 384,
            "max_seq_length": 256,
            "description": "Higher quality than L6, slightly slower (33MB).",
        },
        {
            "model_id": "bge-small-en-v1.5",
            "display_name": "BGE Small EN v1.5",
            "huggingface_repo": "BAAI/bge-small-en-v1.5",
            "dimensions": 384,
            "max_seq_length": 512,
            "description": "Best retrieval quality (33MB). Longer context.",
            "query_prefix": "Represent this sentence for searching relevant passages: ",
        },
    ]

    @property
    def model_configs(self) -> list[dict]:
        """Return embedding model definitions from config, with built-in fallback."""
        return self._data.get("embeddings", {}).get("models", self._DEFAULT_MODELS)

    @property
    def chunk_size(self) -> int:
        """Return the maximum chunk size in characters."""
        return self._data.get("embeddings", {}).get("chunk_size", 512)

    @property
    def chunk_overlap(self) -> int:
        """Return the overlap between consecutive chunks."""
        return self._data.get("embeddings", {}).get("chunk_overlap", 50)

    # --- Storage ---
    @property
    def data_directory(self) -> str:
        """Return the resolved parent data directory (e.g. ./data/)."""
        return str(Path(self.persist_directory).parent)

    @property
    def persist_directory(self) -> str:
        """Return the resolved path for ChromaDB persistence."""
        raw = self._data.get("storage", {}).get(
            "persist_directory", "./data/chromadb"
        )
        return self._resolve_path(raw)

    @property
    def collection_name(self) -> str:
        """Return the ChromaDB collection name."""
        return self._data.get("storage", {}).get(
            "collection_name", "mdkb"
        )

    # --- Core ---

    @property
    def core_features(self) -> dict[str, bool]:
        """Return the core behaviour flags."""
        return dict(self._data.get("core", {}))

    def core_enabled(self, name: str) -> bool:
        """Check whether a core feature is enabled."""
        return self._data.get("core", {}).get(name, False)

    def set_core(self, name: str, enabled: bool) -> None:
        """Set a core feature flag."""
        self._data.setdefault("core", {})[name] = enabled

    # --- MCP ---

    @property
    def mcp_features(self) -> dict[str, bool]:
        """Return the MCP tool enable flags."""
        return dict(self._data.get("mcp", {}))

    def mcp_enabled(self, name: str) -> bool:
        """Check whether an MCP tool is enabled."""
        return self._data.get("mcp", {}).get(name, False)

    def set_mcp_enabled(self, name: str, enabled: bool) -> None:
        """Set an MCP tool enable flag."""
        self._data.setdefault("mcp", {})[name] = enabled

    # --- Plugin Configuration ---

    def plugin_enabled(self, name: str) -> bool:
        """Check whether plugin *name* is enabled via ``plugins.<name>.enabled``."""
        cfg = self._data.get("plugins", {}).get(name, {})
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

    # --- Service Configuration ---

    def get_service_config(self, service_name: str) -> dict:
        """Return config for a shared service from ``services.<name>``."""
        return dict(self._data.get("services", {}).get(service_name, {}))

    def set_service_config(self, service_name: str, config: dict) -> None:
        """Merge *config* into ``services.<name>``."""
        services = self._data.setdefault("services", {})
        existing = services.setdefault(service_name, {})
        existing.update(config)

    # --- Auth ---
    @property
    def api_key(self) -> str:
        """Return the API key for header-based authentication.

        Checked in order: Docker secret ``mdkb_api_key`` > ``MDKB_API_KEY``
        env var.  Empty string means authentication is disabled.
        """
        return _read_secret("mdkb_api_key") or os.environ.get("MDKB_API_KEY", "")

    # --- Server ---
    @property
    def server_host(self) -> str:
        """Return the server bind host (SERVER_HOST env var > settings.yaml > 127.0.0.1)."""
        if os.environ.get("SERVER_HOST"):
            return os.environ["SERVER_HOST"]
        return self._data.get("server", {}).get("host", "127.0.0.1")

    @property
    def server_port(self) -> int:
        """Return the server port number (API_PORT env var > settings.yaml > 9713)."""
        if os.environ.get("API_PORT"):
            try:
                return int(os.environ["API_PORT"])
            except ValueError:
                logger.error("API_PORT env var is not a valid integer: %r", os.environ["API_PORT"])
                raise
        return self._data.get("server", {}).get("port", 9713)

    # --- CORS ---
    @property
    def cors_origins(self) -> list[str]:
        """Return allowed CORS origins.

        CORS_ORIGINS env var (comma-separated) > server.cors_origins in
        settings.yaml > default based on FRONTEND_PORT.
        """
        env_val = os.environ.get("CORS_ORIGINS", "")
        if env_val:
            return [o.strip() for o in env_val.split(",") if o.strip()]
        configured = self._data.get("server", {}).get("cors_origins")
        if configured:
            return list(configured)
        frontend_port = os.environ.get("FRONTEND_PORT", "9714")
        return [f"http://localhost:{frontend_port}"]

    # --- Plans ---
    @property
    def plans_save_directory(self) -> str:
        """Return the resolved path for saving plans."""
        raw = self._data.get("plans", {}).get(
            "save_directory", "./data/plans"
        )
        return self._resolve_path(raw)

    # --- UI ---
    @property
    def file_list_limit(self) -> int:
        """Return the maximum number of files to return in file listings."""
        return self._data.get("ui", {}).get("file_list_limit", 5000)

    # --- Logging ---
    @property
    def log_level(self) -> str:
        """Return the configured log level (INFO or DEBUG)."""
        return self._data.get("logging", {}).get("level", "INFO")

    @log_level.setter
    def log_level(self, value: str):
        """Set the log level."""
        self._data.setdefault("logging", {})["level"] = value

    # --- Raw access ---
    @property
    def raw(self) -> dict:
        """Return the raw configuration dictionary."""
        return self._data

    def set(self, key_path: str, value: Any):
        """Set a value using dot-separated key path."""
        keys = key_path.split(".")
        d = self._data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
