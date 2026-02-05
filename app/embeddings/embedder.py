"""ONNX-based text embedding using ChromaDB's built-in MiniLM model."""

import logging
import os

from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

logger = logging.getLogger(__name__)

# Limit ONNX threads to avoid saturating all CPU cores.
# Default to half the available cores (minimum 1).
# Can be overridden by setting OMP_NUM_THREADS before starting the app.
_DEFAULT_THREADS = str(max(1, (os.cpu_count() or 4) // 2))
os.environ.setdefault("OMP_NUM_THREADS", _DEFAULT_THREADS)


class _EmbeddingCache:
    """Lazy-loading cache for the ONNX embedding function."""

    def __init__(self):
        self._function: ONNXMiniLM_L6_V2 | None = None

    def get(self) -> ONNXMiniLM_L6_V2:
        """Return the cached function, loading on first call."""
        if self._function is None:
            threads = os.environ.get("OMP_NUM_THREADS", _DEFAULT_THREADS)
            logger.info(
                "Loading ONNX embedding model: all-MiniLM-L6-v2 "
                "(threads=%s)", threads,
            )
            self._function = ONNXMiniLM_L6_V2()
            logger.info("Embedding model loaded")
        return self._function


_cache = _EmbeddingCache()


def get_embedding_function() -> ONNXMiniLM_L6_V2:
    """Return the cached ONNX embedding function."""
    return _cache.get()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of text strings into vectors."""
    if not texts:
        return []
    return get_embedding_function()(texts)


def embed_query(query: str) -> list[float]:
    """Embed a single query string into a vector."""
    result = get_embedding_function()([query])
    return result[0]
