import os
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"


def _resolve_env(value: str) -> str:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        return os.environ.get(env_var, "")
    return value


def _resolve_env_recursive(obj: Any) -> Any:
    if isinstance(obj, str):
        return _resolve_env(obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_recursive(v) for v in obj]
    return obj


class Settings:
    _instance: "Settings | None" = None

    def __init__(self, config_path: str | Path | None = None):
        path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        if path.exists():
            with open(path) as f:
                self._data = yaml.safe_load(f) or {}
        else:
            self._data = {}
        self._data = _resolve_env_recursive(self._data)
        self._path = path

    @classmethod
    def get(cls, config_path: str | Path | None = None) -> "Settings":
        if cls._instance is None:
            cls._instance = cls(config_path)
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            yaml.dump(self._data, f, default_flow_style=False, sort_keys=False)

    # --- Sources ---
    @property
    def sources(self) -> list[str]:
        return self._data.get("sources", [])

    @sources.setter
    def sources(self, value: list[str]):
        self._data["sources"] = value

    def add_source(self, path: str):
        if path not in self.sources:
            self.sources.append(path)

    def remove_source(self, path: str):
        if path in self.sources:
            self.sources.remove(path)

    @property
    def global_ignore(self) -> list[str]:
        return self._data.get("global_ignore", [])

    # --- Embeddings ---
    @property
    def embedding_model(self) -> str:
        return self._data.get("embeddings", {}).get("model", "all-MiniLM-L6-v2")

    @property
    def chunk_size(self) -> int:
        return self._data.get("embeddings", {}).get("chunk_size", 512)

    @property
    def chunk_overlap(self) -> int:
        return self._data.get("embeddings", {}).get("chunk_overlap", 50)

    # --- LLM ---
    @property
    def llm_providers(self) -> list[dict]:
        return self._data.get("llm", {}).get("providers", [])

    @property
    def active_provider(self) -> str:
        return self._data.get("llm", {}).get("active_provider", "anthropic")

    @active_provider.setter
    def active_provider(self, value: str):
        self._data.setdefault("llm", {})["active_provider"] = value

    def get_active_llm_config(self) -> dict:
        for p in self.llm_providers:
            if p.get("name") == self.active_provider:
                return p
        return self.llm_providers[0] if self.llm_providers else {}

    @property
    def llm_temperature(self) -> float:
        return self._data.get("llm", {}).get("temperature", 0.3)

    @property
    def llm_max_tokens(self) -> int:
        return self._data.get("llm", {}).get("max_tokens", 2048)

    # --- Retrieval ---
    @property
    def top_k(self) -> int:
        return self._data.get("retrieval", {}).get("top_k", 5)

    @property
    def score_threshold(self) -> float:
        return self._data.get("retrieval", {}).get("score_threshold", 0.3)

    @property
    def hybrid_search(self) -> bool:
        return self._data.get("retrieval", {}).get("hybrid_search", True)

    @property
    def bm25_weight(self) -> float:
        return self._data.get("retrieval", {}).get("bm25_weight", 0.3)

    # --- Storage ---
    @property
    def persist_directory(self) -> str:
        return self._data.get("storage", {}).get("persist_directory", "./data/chromadb")

    @property
    def collection_name(self) -> str:
        return self._data.get("storage", {}).get("collection_name", "mdkb")

    # --- Features ---
    @property
    def features(self) -> dict[str, bool]:
        return self._data.get("features", {})

    def feature_enabled(self, name: str) -> bool:
        return self.features.get(name, False)

    # --- Server ---
    @property
    def server_host(self) -> str:
        return self._data.get("server", {}).get("host", "0.0.0.0")

    @property
    def server_port(self) -> int:
        return self._data.get("server", {}).get("port", 9713)

    # --- Plans ---
    @property
    def plans_save_directory(self) -> str:
        return self._data.get("plans", {}).get("save_directory", "./data/plans")

    # --- Raw access ---
    @property
    def raw(self) -> dict:
        return self._data

    def set(self, key_path: str, value: Any):
        keys = key_path.split(".")
        d = self._data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
