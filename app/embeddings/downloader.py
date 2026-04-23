"""Download and manage ONNX embedding model files."""

import logging
import shutil
import urllib.request
from collections.abc import Callable
from pathlib import Path

from app.config import default_data_dir as _data_dir
from app.embeddings.registry import MODELS

logger = logging.getLogger(__name__)

# Primary model cache — derived from the data directory at import time.
# Lazy resolution: settings aren't loaded yet, so use the same env/platformdirs
# fallback that config uses.
CACHE_DIR = Path(_data_dir()) / "models"
HF_URL = "https://huggingface.co/{repo}/resolve/main/{path}"


def model_dir(model_id: str) -> Path:
    """Return the primary cache directory for a model."""
    return CACHE_DIR / model_id


def _dir_has_model(d: Path, info) -> bool:
    """Check if a directory contains all required model files.

    Also validates that the ONNX model file is not truncated (> 1 KB).
    """
    for f in info.files:
        fp = d / f
        if not fp.exists():
            return False
        if f.endswith(".onnx") and fp.stat().st_size < 1024:
            return False
    return True


def is_installed(model_id: str) -> bool:
    """Check whether all required files for a model exist on disk."""
    info = MODELS.get(model_id)
    if not info:
        return False
    return _dir_has_model(model_dir(model_id), info)


def get_model_path(model_id: str) -> Path:
    """Return the directory containing model files."""
    info = MODELS.get(model_id)
    primary = model_dir(model_id)
    if info and _dir_has_model(primary, info):
        logger.debug("Model '%s' found at %s", model_id, primary)
    else:
        logger.debug("Model '%s' not found, returning default path: %s", model_id, primary)
    return primary


def _format_size(nbytes: int) -> str:
    """Format byte count as human-readable string."""
    if nbytes < 1024:
        return f"{nbytes} B"
    if nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.1f} KB"
    return f"{nbytes / (1024 * 1024):.1f} MB"


def install_from_local(
    model_id: str,
    source_dir: str | Path,
    progress: Callable[[float, str], None] | None = None,
) -> None:
    """Install a model by copying files from a local directory.

    The source directory must contain all files listed in the model's
    registry entry (e.g. onnx/model.onnx, tokenizer.json, etc.).
    """
    info = MODELS[model_id]
    source = Path(source_dir)
    dest = model_dir(model_id)

    missing = [f for f in info.files if not (source / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Source directory {source} is missing required files: {missing}"
        )

    total_files = len(info.files)
    for i, rel_path in enumerate(info.files):
        file_dest = dest / rel_path
        if file_dest.exists():
            continue
        file_dest.parent.mkdir(parents=True, exist_ok=True)
        src_file = source / rel_path
        if progress:
            progress(i / total_files, f"Copying {rel_path}...")
        shutil.copy2(src_file, file_dest)
        logger.info("Copied %s (%s)", rel_path, _format_size(file_dest.stat().st_size))

    if progress:
        progress(1.0, "Done")
    logger.info("Model %s installed from %s", model_id, source)


def install_model(
    model_id: str,
    progress: Callable[[float, str], None] | None = None,
) -> None:
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

        import uuid
        tmp = file_dest.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
        req = urllib.request.Request(url, headers={"User-Agent": "markdownkb/1.0"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            last_logged_pct = -10
            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = int(downloaded * 100 / total)
                        if pct >= last_logged_pct + 10:
                            msg = f"Downloading {rel_path}: {_format_size(downloaded)} / {_format_size(total)} ({pct}%)"
                            logger.info("  %s: %s / %s (%d%%)", rel_path, _format_size(downloaded), _format_size(total), pct)
                            if progress:
                                progress(pct / 100, msg)
                            last_logged_pct = pct
        if total == 0:
            logger.info("  %s: %s downloaded", rel_path, _format_size(downloaded))
        tmp.rename(file_dest)

    if progress:
        progress(1.0, "Done")
    logger.info("Model %s installed to %s", model_id, dest)


def uninstall_model(model_id: str) -> bool:
    """Remove a downloaded model's files from disk.

    Returns True if files were deleted, False if nothing was found.
    """
    primary = model_dir(model_id)
    if primary.exists():
        shutil.rmtree(primary)
        logger.info("Removed model directory: %s", primary)
        return True
    return False


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
            "local_path": info.local_path,
            "huggingface_repo": info.huggingface_repo,
        }
        for info in MODELS.values()
    ]
