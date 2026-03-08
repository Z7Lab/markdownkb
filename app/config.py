"""Application configuration loaded from settings.yaml."""

import logging
import os
import threading
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "settings.yaml"
)


def _resolve_env(value: str) -> str:
    """Replace ${VAR} placeholders with environment variable values."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        resolved = os.environ.get(env_var)
        if resolved is None:
            logger.warning("Environment variable %s is not set, using empty string", env_var)
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


class Settings:
    """Singleton settings manager backed by YAML config file."""

    _instance: "Settings | None" = None
    _class_lock = threading.Lock()

    def __init__(self, config_path: str | Path | None = None):
        path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        if path.exists():
            with open(path, encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
        else:
            self._data = {}
        self._data = _resolve_env_recursive(self._data)
        self._path = path
        self._project_root = path.resolve().parent.parent
        self._lock = threading.Lock()
        self._mcp_cache: dict[str, dict] = {}
        self._mcp_dir = self._path.parent / "mcp"

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

    # --- Sources ---
    @property
    def sources(self) -> list[str]:
        """Return resolved paths for all configured sources."""
        return [
            self._resolve_path(s)
            for s in self._data.get("sources", [])
        ]

    @sources.setter
    def sources(self, value: list[str]):
        """Set the list of source directories."""
        self._data["sources"] = value

    def add_source(self, path: str):
        """Add a source directory if not already present."""
        raw = self._data.setdefault("sources", [])
        if path not in raw and path not in self.sources:
            raw.append(path)

    def remove_source(self, path: str):
        """Remove a source directory from the list."""
        raw = self._data.setdefault("sources", [])
        if path in raw:
            raw.remove(path)
        else:
            # Try matching by resolved path
            resolved = self._resolve_path(path)
            for s in list(raw):
                if self._resolve_path(s) == resolved:
                    raw.remove(s)
                    break

    @property
    def global_ignore(self) -> list[str]:
        """Return glob patterns for files to ignore."""
        return self._data.get("global_ignore", [])

    def add_ignore_pattern(self, pattern: str):
        """Add a glob pattern to the ignore list."""
        patterns = self._data.setdefault("global_ignore", [])
        if pattern not in patterns:
            patterns.append(pattern)

    def remove_ignore_pattern(self, pattern: str):
        """Remove a glob pattern from the ignore list."""
        patterns = self._data.get("global_ignore", [])
        if pattern in patterns:
            patterns.remove(pattern)

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

    # --- LLM ---
    @property
    def llm_providers(self) -> list[dict]:
        """Return the list of LLM provider configurations."""
        return self._data.get("llm", {}).get("providers", [])

    @property
    def active_provider(self) -> str:
        """Return the currently active LLM provider name."""
        return self._data.get("llm", {}).get(
            "active_provider", "anthropic"
        )

    @active_provider.setter
    def active_provider(self, value: str):
        """Set the active LLM provider by name."""
        self._data.setdefault("llm", {})["active_provider"] = value

    def get_active_llm_config(self) -> dict:
        """Return the config dict for the active provider.

        For ollama, the OLLAMA_API_BASE env var overrides api_base from YAML
        so Docker/remote setups work without editing settings.yaml.
        """
        config: dict = {}
        for p in self.llm_providers:
            if p.get("name") == self.active_provider:
                config = p
                break
        if not config:
            if self.llm_providers:
                config = self.llm_providers[0]
            else:
                logger.warning("No LLM providers configured — LLM features will be unavailable")
                return {}

        # Allow OLLAMA_API_BASE env var to override yaml for ollama provider
        if config.get("name") == "ollama" and os.environ.get("OLLAMA_API_BASE"):
            config = {**config, "api_base": os.environ["OLLAMA_API_BASE"]}

        return config

    @property
    def llm_temperature(self) -> float:
        """Return temperature for the active provider, falling back to global default."""
        active = self.get_active_llm_config()
        if "temperature" in active:
            return active["temperature"]
        return self._data.get("llm", {}).get("temperature", 0.3)

    @llm_temperature.setter
    def llm_temperature(self, value: float):
        """Set temperature on the active provider entry."""
        for p in self.llm_providers:
            if p.get("name") == self.active_provider:
                p["temperature"] = value
                return
        # Fallback: set global default
        self._data.setdefault("llm", {})["temperature"] = value

    @property
    def llm_max_tokens(self) -> int:
        """Return max_tokens for the active provider, falling back to global default."""
        active = self.get_active_llm_config()
        if "max_tokens" in active:
            return active["max_tokens"]
        return self._data.get("llm", {}).get("max_tokens", 2048)

    @llm_max_tokens.setter
    def llm_max_tokens(self, value: int):
        """Set max_tokens on the active provider entry."""
        for p in self.llm_providers:
            if p.get("name") == self.active_provider:
                p["max_tokens"] = value
                return
        self._data.setdefault("llm", {})["max_tokens"] = value

    @property
    def llm_num_ctx(self) -> int | None:
        """Return Ollama context window override from active provider (None = model default)."""
        active = self.get_active_llm_config()
        if "num_ctx" in active:
            return active["num_ctx"]
        return self._data.get("llm", {}).get("num_ctx")

    @llm_num_ctx.setter
    def llm_num_ctx(self, value: int | None):
        """Set Ollama context window on the active provider entry."""
        for p in self.llm_providers:
            if p.get("name") == self.active_provider:
                if value is None:
                    p.pop("num_ctx", None)
                else:
                    p["num_ctx"] = value
                return
        if value is None:
            self._data.get("llm", {}).pop("num_ctx", None)
        else:
            self._data.setdefault("llm", {})["num_ctx"] = value

    # --- Retrieval ---
    @property
    def top_k(self) -> int:
        """Return the number of results per search."""
        return self._data.get("retrieval", {}).get("top_k", 5)

    @property
    def score_threshold(self) -> float:
        """Return the minimum similarity score threshold."""
        return self._data.get("retrieval", {}).get(
            "score_threshold", 0.3
        )

    @property
    def hybrid_search(self) -> bool:
        """Return whether hybrid BM25+vector search is enabled."""
        return self._data.get("retrieval", {}).get(
            "hybrid_search", True
        )

    @property
    def bm25_weight(self) -> float:
        """Return the BM25 weight in hybrid search."""
        return self._data.get("retrieval", {}).get("bm25_weight", 0.5)

    @property
    def default_top_k(self) -> int:
        """Return the built-in default top_k value."""
        return 5

    @property
    def default_score_threshold(self) -> float:
        """Return the built-in default score_threshold value."""
        return 0.3

    @property
    def default_hybrid_search(self) -> bool:
        """Return the built-in default hybrid_search value."""
        return True

    @property
    def default_bm25_weight(self) -> float:
        """Return the built-in default bm25_weight value."""
        return 0.5

    @top_k.setter
    def top_k(self, value: int):
        """Set the number of results per search."""
        self._data.setdefault("retrieval", {})["top_k"] = value

    @score_threshold.setter
    def score_threshold(self, value: float):
        """Set the minimum similarity score threshold."""
        self._data.setdefault("retrieval", {})["score_threshold"] = value

    @hybrid_search.setter
    def hybrid_search(self, value: bool):
        """Set whether hybrid BM25+vector search is enabled."""
        self._data.setdefault("retrieval", {})["hybrid_search"] = value

    @bm25_weight.setter
    def bm25_weight(self, value: float):
        """Set the BM25 weight in hybrid search."""
        self._data.setdefault("retrieval", {})["bm25_weight"] = value

    @property
    def intelligent_search_enabled(self) -> bool:
        """Return whether LLM-powered query enhancement is enabled."""
        return self._data.get("retrieval", {}).get(
            "intelligent_search", {}
        ).get("enabled", False)

    @intelligent_search_enabled.setter
    def intelligent_search_enabled(self, value: bool):
        """Enable or disable intelligent search."""
        retrieval = self._data.setdefault("retrieval", {})
        retrieval.setdefault("intelligent_search", {})["enabled"] = value

    @property
    def intelligent_search_extract_keywords(self) -> bool:
        """Return whether to extract keywords in intelligent search."""
        return self._data.get("retrieval", {}).get(
            "intelligent_search", {}
        ).get("extract_keywords", True)

    @property
    def intelligent_search_expand_acronyms(self) -> bool:
        """Return whether to expand acronyms in intelligent search."""
        return self._data.get("retrieval", {}).get(
            "intelligent_search", {}
        ).get("expand_acronyms", True)

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

    # --- Features ---
    @property
    def features(self) -> dict[str, bool]:
        """Return the feature flags dictionary."""
        return self._data.get("features", {})

    def feature_enabled(self, name: str) -> bool:
        """Check whether a named feature is enabled."""
        return self.features.get(name, False)

    # --- MCP Tools Configuration ---
    def _load_mcp_config(self, tool_name: str) -> dict:
        """Load MCP tool config from tool folder + user overrides."""
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

    # --- Auth ---
    @property
    def api_key(self) -> str:
        """Return the API key for header-based authentication.

        Checked in order: MDKB_API_KEY env var > auth.api_key in
        settings.yaml.  Empty string means authentication is disabled.
        """
        if os.environ.get("MDKB_API_KEY"):
            return os.environ["MDKB_API_KEY"]
        return self._data.get("auth", {}).get("api_key", "")

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
            return int(os.environ["API_PORT"])
        return self._data.get("server", {}).get("port", 9713)

    # --- Plans ---
    @property
    def plans_save_directory(self) -> str:
        """Return the resolved path for saving plans."""
        raw = self._data.get("plans", {}).get(
            "save_directory", "./data/plans"
        )
        return self._resolve_path(raw)

    # --- Prompts ---
    _DEFAULT_SYSTEM_PROMPT = (
        "You are mdkb, a personal knowledge base assistant. "
        "You answer questions based on the user's indexed markdown documents.\n\n"
        "Rules:\n"
        "- Answer ONLY based on the provided context. "
        "If the context doesn't contain enough information, say so.\n"
        "- ALWAYS cite sources inline when you reference information. "
        "After each claim or quote, include the source path like this: "
        "(Source: /path/to/file.md). The context provides [Source: ...] tags "
        "— use those paths in your citations.\n"
        "- When synthesizing information from multiple files, "
        "cite each source next to the relevant information.\n"
        "- Be concise but thorough. "
        "Summarize across multiple documents when relevant.\n"
        "- If the user asks about something not in the context, "
        "say \"I don't have information about that in your knowledge base.\"\n"
        "- Preserve technical accuracy "
        "— don't paraphrase code or configuration incorrectly.\n"
        "- NEVER guess or speculate about a file's contents based on its name or path. "
        "If a file is mentioned but its content is not in the provided context, "
        "say you don't have that file indexed — do not say \"this file likely\" "
        "or make assumptions about what it contains.\n"
        "- Use markdown formatting in your responses."
    )

    _DEFAULT_SEARCH_SUMMARY_PROMPT = (
        "You are a knowledge base search assistant. "
        "Provide a focused, concise summary that directly answers "
        "the user's query based on the provided context. "
        "Cite sources using (Source: filename) notation. "
        "If the context doesn't contain enough information, say so clearly. "
        "Keep it brief: 1-2 short paragraphs maximum. Be direct and to the point."
    )

    @property
    def system_prompt(self) -> str:
        """Return the RAG system prompt."""
        return self._data.get("prompts", {}).get(
            "system_prompt", self._DEFAULT_SYSTEM_PROMPT
        )

    @system_prompt.setter
    def system_prompt(self, value: str):
        """Set the RAG system prompt."""
        self._data.setdefault("prompts", {})["system_prompt"] = value

    @property
    def default_system_prompt(self) -> str:
        """Return the built-in default system prompt."""
        return self._DEFAULT_SYSTEM_PROMPT

    @property
    def search_summary_prompt(self) -> str:
        """Return the search summary prompt."""
        return self._data.get("prompts", {}).get(
            "search_summary_prompt", self._DEFAULT_SEARCH_SUMMARY_PROMPT
        )

    @search_summary_prompt.setter
    def search_summary_prompt(self, value: str):
        """Set the search summary prompt."""
        self._data.setdefault("prompts", {})["search_summary_prompt"] = value

    @property
    def default_search_summary_prompt(self) -> str:
        """Return the built-in default search summary prompt."""
        return self._DEFAULT_SEARCH_SUMMARY_PROMPT

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
