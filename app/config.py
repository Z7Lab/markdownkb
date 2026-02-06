"""Application configuration loaded from settings.yaml."""

import os
import threading
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "settings.yaml"
)


def _resolve_env(value: str) -> str:
    """Replace ${VAR} placeholders with environment variable values."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        return os.environ.get(env_var, "")
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
        """Return the config dict for the active provider."""
        for p in self.llm_providers:
            if p.get("name") == self.active_provider:
                return p
        return self.llm_providers[0] if self.llm_providers else {}

    @property
    def llm_temperature(self) -> float:
        """Return the LLM sampling temperature."""
        return self._data.get("llm", {}).get("temperature", 0.3)

    @property
    def llm_max_tokens(self) -> int:
        """Return the maximum tokens for LLM completions."""
        return self._data.get("llm", {}).get("max_tokens", 2048)

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
        return self._data.get("retrieval", {}).get("bm25_weight", 0.3)

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

    # --- Server ---
    @property
    def server_host(self) -> str:
        """Return the server bind host address."""
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
