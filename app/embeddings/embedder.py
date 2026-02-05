import logging

from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

logger = logging.getLogger(__name__)

_ef_cache: ONNXMiniLM_L6_V2 | None = None


def get_embedding_function() -> ONNXMiniLM_L6_V2:
    global _ef_cache
    if _ef_cache is None:
        logger.info("Loading ONNX embedding model: all-MiniLM-L6-v2")
        _ef_cache = ONNXMiniLM_L6_V2()
        logger.info("Embedding model loaded")
    return _ef_cache


def embed_texts(texts: list[str], model_name: str = "") -> list[list[float]]:
    if not texts:
        return []
    ef = get_embedding_function()
    return ef(texts)


def embed_query(query: str, model_name: str = "") -> list[float]:
    ef = get_embedding_function()
    result = ef([query])
    return result[0]
