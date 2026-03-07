"""Registry of ONNX embedding models.

All models are defined in settings.yaml under ``embeddings.models``.
Call ``load_models()`` at startup to populate the registry from config.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default files expected for sentence-transformer ONNX models
_DEFAULT_FILES = (
    "onnx/model.onnx",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "config.json",
    "vocab.txt",
)


@dataclass(frozen=True)
class EmbeddingModelInfo:
    """Metadata for a supported embedding model."""

    model_id: str
    display_name: str
    huggingface_repo: str
    dimensions: int
    max_seq_length: int
    description: str = ""
    query_prefix: str = ""
    onnx_path: str = "onnx/model.onnx"
    tokenizer_path: str = "tokenizer.json"
    files: tuple[str, ...] = field(default_factory=lambda: _DEFAULT_FILES)
    local_path: str = ""


# Active registry — populated by load_models()
MODELS: dict[str, EmbeddingModelInfo] = {}


def load_models(model_configs: list[dict]) -> None:
    """Populate the registry from settings.yaml model definitions.

    Each entry needs at minimum:
        model_id, display_name, huggingface_repo, dimensions, max_seq_length

    Optional: description, query_prefix, onnx_path, tokenizer_path,
    files, local_path
    """
    MODELS.clear()
    for entry in model_configs:
        model_id = entry.get("model_id")
        if not model_id:
            logger.warning("Skipping model entry with no model_id: %s", entry)
            continue

        required = ("display_name", "huggingface_repo", "dimensions", "max_seq_length")
        missing = [k for k in required if k not in entry]
        if missing:
            logger.warning(
                "Skipping model '%s' — missing required fields: %s",
                model_id, missing,
            )
            continue

        files = entry.get("files")
        if files:
            files = tuple(files)

        info = EmbeddingModelInfo(
            model_id=model_id,
            display_name=entry["display_name"],
            huggingface_repo=entry["huggingface_repo"],
            dimensions=entry["dimensions"],
            max_seq_length=entry["max_seq_length"],
            description=entry.get("description", ""),
            query_prefix=entry.get("query_prefix", ""),
            onnx_path=entry.get("onnx_path", "onnx/model.onnx"),
            tokenizer_path=entry.get("tokenizer_path", "tokenizer.json"),
            files=files if files else _DEFAULT_FILES,
            local_path=entry.get("local_path", ""),
        )
        MODELS[model_id] = info
        logger.debug("Registered embedding model: %s", model_id)

    logger.info("Loaded %d embedding model(s) from config", len(MODELS))


def get_model_info(model_id: str) -> EmbeddingModelInfo:
    """Lookup model info by ID. Raises KeyError if not found."""
    return MODELS[model_id]
