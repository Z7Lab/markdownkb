"""Download and manage ONNX embedding model files."""

import logging
from pathlib import Path

import httpx

from app.embeddings.registry import MODELS

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".cache" / "mdkb" / "models"
_CHROMA_BASE = (
    Path.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2"
)
HF_URL = "https://huggingface.co/{repo}/resolve/main/{path}"


def model_dir(model_id: str) -> Path:
    """Return the local cache directory for a model."""
    return CACHE_DIR / model_id


def _chroma_cache_ok() -> bool:
    """Check if ChromaDB's built-in MiniLM-L6-v2 cache is usable."""
    onnx_dir = _CHROMA_BASE / "onnx"
    needed = ("model.onnx", "tokenizer.json", "config.json")
    return all((onnx_dir / f).exists() for f in needed)


def is_installed(model_id: str) -> bool:
    """Check whether all required files for a model exist on disk."""
    info = MODELS.get(model_id)
    if not info:
        return False
    if model_id == "all-MiniLM-L6-v2" and _chroma_cache_ok():
        return True
    d = model_dir(model_id)
    return all((d / f).exists() for f in info.files)


def get_model_path(model_id: str) -> Path:
    """Return the directory containing model files."""
    if model_id == "all-MiniLM-L6-v2":
        our = model_dir(model_id)
        if (our / "onnx" / "model.onnx").exists():
            return our
        if _chroma_cache_ok():
            # ChromaDB puts all files inside onnx/ subdir. Return the
            # parent so onnx/model.onnx resolves correctly.
            return _CHROMA_BASE
    return model_dir(model_id)


def install_model(model_id: str) -> None:
    """Download all files for a model from HuggingFace."""
    info = MODELS[model_id]
    dest = model_dir(model_id)

    for rel_path in info.files:
        file_dest = dest / rel_path
        if file_dest.exists():
            continue

        file_dest.parent.mkdir(parents=True, exist_ok=True)
        url = HF_URL.format(repo=info.huggingface_repo, path=rel_path)
        logger.info("Downloading %s", url)

        tmp = file_dest.with_suffix(".tmp")
        with httpx.stream("GET", url, timeout=120) as resp:
            resp.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        tmp.rename(file_dest)

    logger.info("Model %s installed to %s", model_id, dest)


def list_models_with_status() -> list[dict]:
    """Return all registered models with their installation status."""
    return [
        {
            "model_id": info.model_id,
            "display_name": info.display_name,
            "dimensions": info.dimensions,
            "max_seq_length": info.max_seq_length,
            "description": info.description,
            "installed": is_installed(info.model_id),
        }
        for info in MODELS.values()
    ]
