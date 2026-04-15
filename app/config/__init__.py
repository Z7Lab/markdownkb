"""Application configuration loaded from settings.yaml.

The Settings class is composed from domain-specific mixins:
- SourcesMixin: source directories, project roots, ignore patterns
- LLMMixin: LLM providers, active_provider, temperature, key resolution
- RetrievalMixin: top_k, thresholds, hybrid search, BM25
- PromptsMixin: prompt template loading, caching, overrides
- MCPMixin: MCP tool configuration CRUD

Settings layout (post-migration)::

    core:        # behaviour toggles that aren't plugins
    mcp:         # MCP tool enable flags (read_only, save_document, etc.)
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
from app.config._migrations import migrate_num_ctx, migrate_settings
from app.config._paths import (
    DEFAULT_CONFIG_PATH as _DEFAULT_CONFIG_PATH,
    SECRETS_DIR as _SECRETS_DIR,
    data_secrets_dir as _data_secrets_dir,
    default_data_dir,
    read_secret as _read_secret,
    resolve_env as _resolve_env,
    resolve_env_recursive as _resolve_env_recursive,
)

logger = logging.getLogger(__name__)


# Migration helpers retained as private names for callers that imported them
# from this module before they were extracted.
_migrate_settings = migrate_settings
_migrate_num_ctx = migrate_num_ctx


class Settings(SourcesMixin, LLMMixin, RetrievalMixin, PromptsMixin, MCPMixin):
    """Singleton settings manager backed by YAML config file.

    Environment variable substitution (``${VAR}`` in ``settings.yaml``) is
    performed at ``__init__`` and ``reload()`` time only — see
    :func:`_resolve_env_recursive` for details. A small number of properties
    (``cors_origins``, ``server_host``) read ``os.environ`` directly and
    therefore do reflect changes per request; everything else requires
    ``reload()`` to pick up env-var mutations.
    """

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
        migrated = _migrate_settings(self._data)
        if _migrate_num_ctx(self._data):
            migrated = True
        if migrated:
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

    @property
    def embedding_provider(self) -> str:
        """Return 'local' (ONNX) or 'remote' (Ollama/OpenAI-compatible)."""
        return self._data.get("embeddings", {}).get("provider", "local")

    @embedding_provider.setter
    def embedding_provider(self, value: str):
        self._data.setdefault("embeddings", {})["provider"] = value

    @property
    def embedding_remote_config(self) -> dict | None:
        """Return remote embedding config or None if provider is local."""
        if self.embedding_provider != "remote":
            return None
        emb = self._data.get("embeddings", {})
        api_base = emb.get("api_base", "")
        if not api_base:
            return None
        # Resolve API key: check secrets, then env, then config
        api_type = emb.get("api_type", "ollama")
        api_key = ""
        if api_type == "openai":
            api_key = self.resolve_provider_key("embedding") or emb.get("api_key", "")
        return {
            "model": emb.get("remote_model", "nomic-embed-text"),
            "api_base": api_base,
            "api_type": api_type,
            "api_key": api_key,
        }

    def update_embedding_remote_config(self, api_base: str, remote_model: str, api_type: str) -> None:
        """Set remote embedding provider fields (api_base, remote_model, api_type)."""
        emb = self._data.setdefault("embeddings", {})
        emb["api_base"] = api_base
        emb["remote_model"] = remote_model
        emb["api_type"] = api_type

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
            "description": "Best retrieval quality (133MB). 512 token context.",
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
        """Return the data directory for all persistent state.

        Resolution order:
        1. ``storage.data_directory`` in settings.yaml (explicit override)
        2. ``MARKDOWNKB_DATA_DIR`` environment variable (Docker sets this)
        3. ``platformdirs.user_data_dir("markdownkb")`` OS-appropriate default:
           - Linux:   ``~/.local/share/markdownkb``
           - macOS:   ``~/Library/Application Support/markdownkb``
           - Windows: ``%APPDATA%\\markdownkb``
        """
        raw = self._data.get("storage", {}).get("data_directory", "")
        if raw:
            return self._resolve_path(raw)
        return default_data_dir()

    @property
    def persist_directory(self) -> str:
        """Return the resolved path for ChromaDB persistence."""
        raw = self._data.get("storage", {}).get("persist_directory", "")
        if raw:
            return self._resolve_path(raw)
        return str(Path(self.data_directory) / "chromadb")

    @property
    def collection_name(self) -> str:
        """Return the ChromaDB collection name."""
        return self._data.get("storage", {}).get(
            "collection_name", "markdownkb"
        )

    # --- Core ---

    # Defaults for known core flags. Anything missing from settings.yaml
    # falls back to the value here when the flag is read. Keys that should
    # default to True live here; everything else defaults to False.
    CORE_FEATURE_DEFAULTS: dict[str, bool] = {
        "versioning": True,
    }

    @property
    def core_features(self) -> dict[str, bool]:
        """Return the core behaviour flags (merged with defaults for known keys)."""
        configured = dict(self._data.get("core", {}))
        for k, v in self.CORE_FEATURE_DEFAULTS.items():
            configured.setdefault(k, v)
        return configured

    def core_enabled(self, name: str) -> bool:
        """Check whether a core feature is enabled."""
        core = self._data.get("core", {})
        if name in core:
            return bool(core[name])
        return self.CORE_FEATURE_DEFAULTS.get(name, False)

    # --- Versioning ---

    @property
    def versioning_enabled(self) -> bool:
        """Global kill-switch for git-based versioning of writable sources.

        Lives under ``core.versioning`` for consistency with other toggles
        (file_watcher, rag_chat, etc.). Defaults to True.
        """
        return self.core_enabled("versioning")

    @property
    def versioning_root(self) -> str:
        """Directory where per-source managed repos live."""
        override = self._data.get("versioning", {}).get("root", "")
        if override:
            return self._resolve_path(override)
        return str(Path(self.data_directory) / "versioning")

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

    def set_mcp_allowed_hosts(self, hosts: list[str]) -> None:
        """Replace the mcp.allowed_hosts list (DNS rebinding protection)."""
        self._data.setdefault("mcp", {})["allowed_hosts"] = [str(h) for h in hosts]

    def set_mcp_allowed_origins(self, origins: list[str]) -> None:
        """Replace the mcp.allowed_origins list (cross-origin request protection)."""
        self._data.setdefault("mcp", {})["allowed_origins"] = [str(o) for o in origins]

    def set_mcp_rate_limit(self, per_minute: int) -> None:
        """Set the per-key request rate cap. 0 disables rate limiting."""
        self._data.setdefault("mcp", {})["rate_limit_per_minute"] = max(0, int(per_minute))

    # --- Plugin Configuration ---

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

        Checked in order: Docker secret ``markdownkb_api_key`` >
        ``MARKDOWNKB_API_KEY`` env var.  Empty string means authentication
        is disabled.
        """
        return _read_secret("markdownkb_api_key") or os.environ.get("MARKDOWNKB_API_KEY", "")

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
        raw = self._data.get("plans", {}).get("save_directory", "")
        if raw:
            return self._resolve_path(raw)
        return str(Path(self.data_directory) / "plans")

    # --- UI ---
    @property
    def file_list_limit(self) -> int:
        """Return the maximum number of files to return in file listings."""
        return self._data.get("ui", {}).get("file_list_limit", 5000)

    # --- Bucket mounts ---

    @property
    def bucket_mount_configs(self) -> list[dict]:
        """Read-only mount configs for bucket source paths that need Docker mounts."""
        paths = self._data.get("bucket_mounts", [])
        return [{"path": p, "writable": False} for p in paths if p]

    def add_bucket_mount(self, path: str) -> bool:
        """Add a path to bucket_mounts if not already present. Returns True if added."""
        mounts = self._data.setdefault("bucket_mounts", [])
        if path not in mounts:
            mounts.append(path)
            return True
        return False

    def remove_bucket_mount(self, path: str):
        """Remove a path from bucket_mounts."""
        mounts = self._data.get("bucket_mounts", [])
        self._data["bucket_mounts"] = [m for m in mounts if m != path]

    def set_bucket_mounts(self, paths: list[str]):
        """Replace the full bucket_mounts list (used to clean up after bucket deletion)."""
        self._data["bucket_mounts"] = paths

    # --- Logging ---
    @property
    def log_level(self) -> str:
        """Return the configured log level (INFO or DEBUG)."""
        return self._data.get("logging", {}).get("level", "INFO")

    @log_level.setter
    def log_level(self, value: str):
        """Set the log level."""
        self._data.setdefault("logging", {})["level"] = value

    # --- Dashboard Widgets ---
    @property
    def dashboard_widgets(self) -> dict[str, bool]:
        """Return the dashboard widget visibility preferences."""
        return dict(self._data.get("dashboard_widgets", {}))

    def set_dashboard_widget_enabled(self, widget_name: str, enabled: bool) -> None:
        """Set the visibility of a dashboard widget."""
        self._data.setdefault("dashboard_widgets", {})[widget_name] = enabled

    def widget_visible(self, widget_name: str) -> bool:
        """Check whether a dashboard widget is visible to the user."""
        return self._data.get("dashboard_widgets", {}).get(widget_name, True)

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
