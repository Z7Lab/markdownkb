"""Application configuration loaded from settings.yaml.

The Settings class is composed from domain-specific mixins:
- SourcesMixin: source directories, project roots, ignore patterns
- LLMMixin: LLM providers, active_provider, temperature, key resolution
- RetrievalMixin: top_k, thresholds, hybrid search, BM25
- PromptsMixin: prompt template loading, caching, overrides
- MCPMixin: MCP tool configuration CRUD
- EmbeddingsMixin: embedding model, provider, chunking
- StorageMixin: data dir, ChromaDB persistence, collection name
- PluginsMixin: plugin and shared-service config CRUD

Settings layout (post-migration)::

    core:        # behaviour toggles that aren't plugins
    mcp:         # MCP tool enable flags
    plugins:     # each plugin: enabled + its config together
    services:    # shared service config (deep_research, etc.)

Legacy ``features:`` / flat ``plugins:`` layouts are auto-migrated on
first load and persisted back to disk.
"""

import logging
import os
import threading
from pathlib import Path

import yaml

from app.config.embeddings import EmbeddingsMixin
from app.config.llm import LLMMixin
from app.config.mcp import MCPMixin
from app.config.plugins import PluginsMixin
from app.config.prompts import PromptsMixin
from app.config.retrieval import RetrievalMixin
from app.config.sources import SourcesMixin
from app.config.storage import StorageMixin
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
from app.config._validate import SettingsValidationError, validate as _validate_settings

logger = logging.getLogger(__name__)


# Migration helpers retained as private names for callers that imported them
# from this module before they were extracted.
_migrate_settings = migrate_settings
_migrate_num_ctx = migrate_num_ctx


class Settings(
    SourcesMixin,
    LLMMixin,
    RetrievalMixin,
    PromptsMixin,
    MCPMixin,
    EmbeddingsMixin,
    StorageMixin,
    PluginsMixin,
):
    """Singleton settings manager backed by YAML config file.

    Environment variable substitution (``${VAR}`` in ``settings.yaml``) is
    performed at ``__init__`` and ``reload()`` time only. A small number of
    properties (``cors_origins``, ``server_host``) read ``os.environ``
    directly and reflect changes per request; everything else requires
    ``reload()`` to pick up env-var mutations.
    """

    _instance: "Settings | None" = None
    _class_lock = threading.Lock()

    # Core-feature defaults for keys that should default to True when missing.
    CORE_FEATURE_DEFAULTS: dict[str, bool] = {
        "versioning": True,
    }

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
        self._loaded_mtime: float = path.stat().st_mtime if path.exists() else 0.0

        migrated = _migrate_settings(self._data)
        if _migrate_num_ctx(self._data):
            migrated = True
        if migrated:
            self.save()

        _validate_settings(self._data)

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
        """Re-read settings.yaml from disk and update the live instance."""
        with self._lock:
            if self._path.exists():
                with open(self._path, encoding="utf-8") as f:
                    self._data = yaml.safe_load(f) or {}
                self._using_defaults = False
            else:
                self._data = {}
                self._using_defaults = True
            self._data = _resolve_env_recursive(self._data)
            _validate_settings(self._data)
            self._mcp_cache.clear()
            self._prompt_cache.clear()
            self._loaded_mtime = self._path.stat().st_mtime if self._path.exists() else 0.0
            logger.info("Settings reloaded from %s", self._path)

    @property
    def is_dirty(self) -> bool:
        """Return True if settings.yaml has been modified since it was last loaded."""
        if not self._path.exists():
            return False
        return self._path.stat().st_mtime > self._loaded_mtime

    def save(self):
        """Write current configuration back to the YAML file."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                yaml.dump(self._data, f, default_flow_style=False, sort_keys=False)
            self._loaded_mtime = self._path.stat().st_mtime

    def _resolve_path(self, p: str) -> str:
        """Resolve a relative path against the project root."""
        path = Path(p)
        if not path.is_absolute():
            path = self._project_root / path
        return str(path.resolve())

    # --- Core features ---

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

    def set_core(self, name: str, enabled: bool) -> None:
        """Set a core feature flag."""
        self._data.setdefault("core", {})[name] = enabled

    # --- Versioning ---

    @property
    def versioning_enabled(self) -> bool:
        """Global kill-switch for git-based versioning of writable sources."""
        return self.core_enabled("versioning")

    @property
    def versioning_root(self) -> str:
        """Directory where per-source managed repos live."""
        override = self._data.get("versioning", {}).get("root", "")
        if override:
            return self._resolve_path(override)
        return str(Path(self.data_directory) / "versioning")

    # --- MCP flags ---

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

    # --- Auth / Server / CORS ---

    @property
    def api_key(self) -> str:
        """Return the API key for header-based authentication.

        Checked in order: Docker secret ``markdownkb_api_key`` >
        ``MARKDOWNKB_API_KEY`` env var. Empty string means authentication
        is disabled.
        """
        return _read_secret("markdownkb_api_key") or os.environ.get("MARKDOWNKB_API_KEY", "")

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

    @property
    def cors_origins(self) -> list[str]:
        """Return allowed CORS origins (env var > settings > default)."""
        env_val = os.environ.get("CORS_ORIGINS", "")
        if env_val:
            return [o.strip() for o in env_val.split(",") if o.strip()]
        configured = self._data.get("server", {}).get("cors_origins")
        if configured:
            return list(configured)
        frontend_port = os.environ.get("FRONTEND_PORT", "9714")
        return [f"http://localhost:{frontend_port}"]

    # --- Misc ---

    @property
    def plans_save_directory(self) -> str:
        """Return the resolved path for saving plans."""
        raw = self._data.get("plans", {}).get("save_directory", "")
        if raw:
            return self._resolve_path(raw)
        return str(Path(self.data_directory) / "plans")

    @property
    def file_list_limit(self) -> int:
        """Return the maximum number of files to return in file listings."""
        return self._data.get("ui", {}).get("file_list_limit", 5000)

    # --- Project layout ---

    @property
    def project_root(self) -> Path:
        """Absolute project root derived from the config file location."""
        return self._path.resolve().parent.parent

    @property
    def config_path(self) -> Path:
        """Path of the loaded settings.yaml — read-only public accessor."""
        return self._path

    # --- Bucket mounts ---

    @property
    def bucket_mounts(self) -> list[str]:
        """Return a copy of the configured bucket mount paths."""
        return list(self._data.get("bucket_mounts", []))

    @property
    def bucket_mount_configs(self) -> list[dict]:
        """Read-only mount configs for bucket source paths that need Docker mounts."""
        paths = self._data.get("bucket_mounts", [])
        return [{"path": p, "writable": False} for p in paths if p]

    def add_bucket_mount(self, path: str) -> bool:
        """Add a path to bucket_mounts if not already present. Returns True if added."""
        with self._lock:
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
