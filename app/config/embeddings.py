"""Embedding model configuration mixin."""


class EmbeddingsMixin:
    """Embedding model config: provider, model, remote settings, chunking."""

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
            "description": "Fast, good retrieval quality (133MB). 512 token context.",
            "query_prefix": "Represent this sentence for searching relevant passages: ",
        },
        {
            "model_id": "nomic-embed-text-v1.5",
            "display_name": "Nomic Embed Text v1.5",
            "huggingface_repo": "nomic-ai/nomic-embed-text-v1.5",
            "dimensions": 768,
            "max_seq_length": 8192,
            "description": "Best retrieval quality, 8192 token context (130MB). Recommended.",
            "query_prefix": "search_query: ",
            "onnx_path": "onnx/model_quantized.onnx",
            "files": [
                "onnx/model_quantized.onnx",
                "tokenizer.json",
                "tokenizer_config.json",
                "special_tokens_map.json",
                "config.json",
            ],
        },
    ]

    @property
    def embedding_model(self) -> str:
        """Return the configured embedding model name."""
        return self._data.get("embeddings", {}).get("model", "all-MiniLM-L6-v2")

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
