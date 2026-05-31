"""Audio transcription: local faster-whisper or remote OpenAI-compatible API."""

import logging
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"}
AUDIO_MIME_PREFIXES = {"audio/"}

# Available Whisper models with display metadata
WHISPER_MODELS: dict[str, dict] = {
    "tiny":     {"label": "Tiny",     "size": "~75 MB",   "size_bytes": 78_000_000},
    "small":    {"label": "Small",    "size": "~244 MB",  "size_bytes": 244_000_000},
    "medium":   {"label": "Medium",   "size": "~769 MB",  "size_bytes": 769_000_000},
    "large-v2": {"label": "Large v2", "size": "~1.5 GB",  "size_bytes": 1_528_000_000},
    "large-v3": {"label": "Large v3", "size": "~1.5 GB",  "size_bytes": 1_528_000_000},
}


# -- Model cache helpers --

def _model_cache_dir(model_size: str, data_dir: str) -> Path:
    """Return the local cache directory for a given model size."""
    return Path(data_dir) / "whisper" / f"faster-whisper-{model_size}"


def is_available() -> bool:
    """Return True if faster-whisper is importable."""
    import importlib.util
    return importlib.util.find_spec("faster_whisper") is not None


def is_model_installed(model_size: str, data_dir: str) -> bool:
    """Return True if model weights are already downloaded."""
    d = _model_cache_dir(model_size, data_dir)
    return (d / "config.json").exists() and any(d.glob("model*.bin"))


def uninstall_model(model_size: str, data_dir: str) -> bool:
    """Remove downloaded model weights. Returns True if anything was deleted."""
    d = _model_cache_dir(model_size, data_dir)
    if d.exists():
        shutil.rmtree(d)
        logger.info("Removed Whisper model directory: %s", d)
        return True
    return False


_HF_URL = "https://huggingface.co/{repo}/resolve/main/{file}"
_MODEL_FILES = ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"]


def download_model(
    model_size: str,
    data_dir: str,
    progress: Callable[[float, str], None] | None = None,
) -> None:
    """
    Download faster-whisper model weights directly from HuggingFace.

    Uses plain urllib.request so HuggingFace's XET/S3 redirects are followed
    transparently without needing huggingface_hub's caching machinery or a
    home directory inside the container.
    """
    import urllib.request

    repo = f"Systran/faster-whisper-{model_size}"
    dest = _model_cache_dir(model_size, data_dir)
    dest.mkdir(parents=True, exist_ok=True)

    total_bytes = WHISPER_MODELS.get(model_size, {}).get("size_bytes", 0)
    downloaded_so_far = 0

    logger.info("Downloading faster-whisper-%s to %s", model_size, dest)

    for rel_path in _MODEL_FILES:
        out_path = dest / rel_path
        if out_path.exists():
            downloaded_so_far += out_path.stat().st_size
            logger.info("  %s already present, skipping", rel_path)
            continue

        url = _HF_URL.format(repo=repo, file=rel_path)
        tmp_path = out_path.with_suffix(".tmp")
        req = urllib.request.Request(url, headers={"User-Agent": "markdownkb/1.0"})

        logger.info("  Downloading %s", rel_path)
        with urllib.request.urlopen(req, timeout=600) as resp:
            file_total = int(resp.headers.get("Content-Length", 0))
            file_done = 0
            with open(tmp_path, "wb") as fh:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    fh.write(chunk)
                    file_done += len(chunk)
                    if progress:
                        mb_done = file_done / (1024 * 1024)
                        if file_total > 0:
                            mb_total = file_total / (1024 * 1024)
                            frac = min(file_done / file_total, 0.99)
                            progress(frac, f"Downloading {rel_path}: {mb_done:.0f} / {mb_total:.0f} MB")
                        else:
                            progress(0.5, f"Downloading {rel_path}: {mb_done:.0f} MB")

        tmp_path.rename(out_path)
        downloaded_so_far += file_done
        logger.info("  %s done (%d bytes)", rel_path, file_done)

    logger.info("Download complete: faster-whisper-%s", model_size)
    if progress:
        progress(1.0, "Done")


def list_models_with_status(data_dir: str) -> list[dict]:
    """Return all Whisper models with their installation status."""
    return [
        {
            "model_size": size,
            "label": info["label"],
            "size": info["size"],
            "installed": is_model_installed(size, data_dir),
        }
        for size, info in WHISPER_MODELS.items()
    ]


# -- Transcription --

def transcribe_path(
    audio_path: Path,
    model_size: str = "small",
    data_dir: str | None = None,
    progress: Callable[[float, str], None] | None = None,
) -> str:
    """Transcribe an audio file using faster-whisper. Returns transcript text.

    When *progress* is supplied it is called with ``(fraction, message)`` as
    each segment is decoded, where ``fraction`` is ``segment.end / duration``.
    faster-whisper decodes lazily, so iterating ``segments`` is what actually
    drives the transcription forward.
    """
    from faster_whisper import WhisperModel

    # Use pre-downloaded local weights when available; fall back to auto-download.
    if data_dir and is_model_installed(model_size, data_dir):
        model_source: str = str(_model_cache_dir(model_size, data_dir))
        logger.info("Loading Whisper model from local cache: %s", model_source)
    else:
        model_source = model_size
        logger.info("Loading Whisper model '%s' (may auto-download)...", model_size)

    if progress:
        progress(0.0, "Loading transcription model…")

    model = WhisperModel(model_source, device="cpu", compute_type="int8")

    logger.info("Transcribing %s...", audio_path.name)
    segments, info = model.transcribe(str(audio_path), beam_size=5)

    duration = getattr(info, "duration", 0.0) or 0.0
    parts: list[str] = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            parts.append(text)
        if progress and duration > 0:
            frac = min(max(seg.end / duration, 0.0), 0.99)
            mins = int(duration // 60)
            secs = int(duration % 60)
            progress(frac, f"Transcribing… {int(seg.end)}s / {mins}:{secs:02d}")

    transcript = " ".join(parts)
    logger.info(
        "Transcription complete: %d chars, detected language '%s'",
        len(transcript), info.language,
    )
    if progress:
        progress(1.0, "Transcription complete")
    return transcript


# -- Remote transcription --

def transcribe_remote(audio_path: Path, api_base: str, api_key: str = "") -> str:
    """
    Transcribe an audio file via an OpenAI-compatible transcription API.

    POSTs to ``{api_base}/v1/audio/transcriptions`` (strips trailing slash and
    any existing ``/v1`` suffix so both bare base URLs and full URLs work).
    """
    import httpx
    from app.security import validate_api_base

    validate_api_base(api_base)

    base = api_base.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    url = f"{base}/audio/transcriptions"

    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    with audio_path.open("rb") as fh:
        files = {"file": (audio_path.name, fh, "application/octet-stream")}
        data = {"model": "whisper-1", "response_format": "text"}
        logger.info("Sending %s to remote transcription API: %s", audio_path.name, url)
        resp = httpx.post(url, headers=headers, files=files, data=data, timeout=300)

    resp.raise_for_status()
    transcript = resp.text.strip()
    logger.info("Remote transcription complete: %d chars", len(transcript))
    return transcript


# -- markitdown integration --

def make_markitdown_converter(
    model_size: str = "small",
    data_dir: str | None = None,
    provider: str = "local",
    api_base: str = "",
    api_key: str = "",
):
    """
    Build a markitdown DocumentConverter for audio transcription.

    When ``provider`` is ``"remote"`` a lightweight HTTP converter is returned
    that calls an OpenAI-compatible ``/v1/audio/transcriptions`` endpoint.
    When ``provider`` is ``"local"`` (default) faster-whisper is used.

    Returns None if markitdown is unavailable (shouldn't happen in practice).
    """
    try:
        from markitdown import DocumentConverter, DocumentConverterResult, StreamInfo
    except ImportError:
        logger.warning("markitdown not available — audio converter disabled")
        return None

    if provider == "remote":
        class RemoteWhisperConverter(DocumentConverter):
            """Transcribes audio via a remote OpenAI-compatible API."""

            def accepts(self, file_stream: BinaryIO, stream_info: StreamInfo, **kwargs: Any) -> bool:
                ext = (stream_info.extension or "").lower()
                mime = (stream_info.mimetype or "").lower()
                return ext in AUDIO_EXTENSIONS or any(mime.startswith(p) for p in AUDIO_MIME_PREFIXES)

            def convert(
                self, file_stream: BinaryIO, stream_info: StreamInfo, **kwargs: Any
            ) -> DocumentConverterResult:
                suffix = (stream_info.extension or ".mp3").lower()
                fd, tmp = tempfile.mkstemp(suffix=suffix)
                try:
                    os.close(fd)
                    with open(tmp, "wb") as f:
                        shutil.copyfileobj(file_stream, f)
                    transcript = transcribe_remote(Path(tmp), api_base=api_base, api_key=api_key)
                    md = f"### Audio Transcript\n\n{transcript}" if transcript else \
                         "### Audio Transcript\n\n*(no speech detected)*"
                    return DocumentConverterResult(markdown=md)
                except Exception as exc:
                    logger.error("Remote transcription failed: %s", exc)
                    raise
                finally:
                    Path(tmp).unlink(missing_ok=True)

        return RemoteWhisperConverter()

    # Local provider (faster-whisper)
    class WhisperAudioConverter(DocumentConverter):
        """Transcribes audio files to markdown using faster-whisper (local, CPU)."""

        def accepts(self, file_stream: BinaryIO, stream_info: StreamInfo, **kwargs: Any) -> bool:
            ext = (stream_info.extension or "").lower()
            mime = (stream_info.mimetype or "").lower()
            return ext in AUDIO_EXTENSIONS or any(mime.startswith(p) for p in AUDIO_MIME_PREFIXES)

        def convert(
            self, file_stream: BinaryIO, stream_info: StreamInfo, **kwargs: Any
        ) -> DocumentConverterResult:
            suffix = (stream_info.extension or ".mp3").lower()
            fd, tmp = tempfile.mkstemp(suffix=suffix)
            try:
                os.close(fd)
                with open(tmp, "wb") as f:
                    shutil.copyfileobj(file_stream, f)
                transcript = transcribe_path(Path(tmp), model_size=model_size, data_dir=data_dir)
                md = f"### Audio Transcript\n\n{transcript}" if transcript else \
                     "### Audio Transcript\n\n*(no speech detected)*"
                return DocumentConverterResult(markdown=md)
            except Exception as exc:
                logger.error("Whisper transcription failed: %s", exc)
                raise
            finally:
                Path(tmp).unlink(missing_ok=True)

    return WhisperAudioConverter()
