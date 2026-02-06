"""Registry of supported ONNX embedding models."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmbeddingModelInfo:
    """Metadata for a supported embedding model."""

    model_id: str
    display_name: str
    huggingface_repo: str
    dimensions: int
    max_seq_length: int
    description: str
    query_prefix: str = ""
    onnx_path: str = "onnx/model.onnx"
    tokenizer_path: str = "tokenizer.json"
    files: tuple[str, ...] = field(default_factory=tuple)


MODELS: dict[str, EmbeddingModelInfo] = {
    "all-MiniLM-L6-v2": EmbeddingModelInfo(
        model_id="all-MiniLM-L6-v2",
        display_name="MiniLM L6 v2",
        huggingface_repo="sentence-transformers/all-MiniLM-L6-v2",
        dimensions=384,
        max_seq_length=256,
        description="Fast, lightweight (23MB). Good general purpose.",
        files=(
            "onnx/model.onnx",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "config.json",
            "vocab.txt",
        ),
    ),
    "all-MiniLM-L12-v2": EmbeddingModelInfo(
        model_id="all-MiniLM-L12-v2",
        display_name="MiniLM L12 v2",
        huggingface_repo="sentence-transformers/all-MiniLM-L12-v2",
        dimensions=384,
        max_seq_length=256,
        description="Higher quality than L6, slightly slower (33MB).",
        files=(
            "onnx/model.onnx",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "config.json",
            "vocab.txt",
        ),
    ),
    "bge-small-en-v1.5": EmbeddingModelInfo(
        model_id="bge-small-en-v1.5",
        display_name="BGE Small EN v1.5",
        huggingface_repo="BAAI/bge-small-en-v1.5",
        dimensions=384,
        max_seq_length=512,
        description="Best retrieval quality (33MB). Longer context.",
        query_prefix="Represent this sentence for searching relevant passages: ",
        files=(
            "onnx/model.onnx",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "config.json",
            "vocab.txt",
        ),
    ),
}


def get_model_info(model_id: str) -> EmbeddingModelInfo:
    """Lookup model info by ID. Raises KeyError if not found."""
    return MODELS[model_id]
