"""Converter endpoints — batch convert documents to markdown via markitdown."""

import logging
import os
import shutil
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_settings, get_store, get_tracking
from app.events import IndexEvent, event_bus
from app.ingestion.indexer import ReindexError, reindex_file
from app.ratelimit import HEAVY, STANDARD, limiter
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/converter", tags=["converter"])

# All formats grouped by sub-converter.
# "misc" formats need no extra dependencies — base markitdown handles them.
_FORMATS_BY_SUBCONVERTER: dict[str, dict[str, dict]] = {
    "pdf": {
        "pdf": {"extensions": [".pdf"], "label": "PDF"},
    },
    "office": {
        "docx": {"extensions": [".docx"], "label": "Microsoft Word"},
        "pptx": {"extensions": [".pptx"], "label": "PowerPoint"},
        "xlsx": {"extensions": [".xlsx"], "label": "Excel (xlsx)"},
        "xls":  {"extensions": [".xls"],  "label": "Excel (xls)"},
    },
    "audio": {
        "mp3":  {"extensions": [".mp3"],         "label": "MP3"},
        "wav":  {"extensions": [".wav"],         "label": "WAV"},
        "m4a":  {"extensions": [".m4a"],         "label": "M4A"},
        "ogg":  {"extensions": [".ogg"],         "label": "OGG"},
        "flac": {"extensions": [".flac"],        "label": "FLAC"},
        "webm": {"extensions": [".webm"],        "label": "WebM Audio"},
    },
    "misc": {
        "html":  {"extensions": [".html", ".htm"], "label": "HTML"},
        "epub":  {"extensions": [".epub"],          "label": "EPUB"},
        "csv":   {"extensions": [".csv"],            "label": "CSV"},
        "txt":   {"extensions": [".txt"],            "label": "Plain Text"},
        "rst":   {"extensions": [".rst"],            "label": "reStructuredText"},
        "rtf":   {"extensions": [".rtf"],            "label": "Rich Text"},
        "odt":   {"extensions": [".odt"],            "label": "LibreOffice"},
        "ipynb": {"extensions": [".ipynb"],          "label": "Jupyter Notebook"},
        "msg":   {"extensions": [".msg"],            "label": "Outlook Message"},
    },
}

# Flat lookup: format name → {extensions, label, subconverter}
ALL_FORMATS: dict[str, dict] = {
    name: {**info, "subconverter": sub}
    for sub, formats in _FORMATS_BY_SUBCONVERTER.items()
    for name, info in formats.items()
}

# Extension → format name (for upload routing)
_EXT_TO_FORMAT: dict[str, str] = {
    ext: name
    for name, info in ALL_FORMATS.items()
    for ext in info["extensions"]
}


def _plugin_config(settings: Settings) -> dict:
    return settings.get_plugin_config("converter")


def _enabled_formats(settings: Settings) -> dict[str, dict]:
    """Return the subset of ALL_FORMATS whose sub-converter is enabled in config."""
    cfg = _plugin_config(settings)
    return {
        name: info
        for name, info in ALL_FORMATS.items()
        if cfg.get(f"{info['subconverter']}_enabled", True)
    }


def _enabled_extensions(settings: Settings) -> set[str]:
    return {ext for info in _enabled_formats(settings).values() for ext in info["extensions"]}


def _has_transcript_support() -> bool:
    import importlib.util
    return importlib.util.find_spec("youtube_transcript_api") is not None


def _has_audio_support() -> bool:
    from app.plugins.converter.audio import is_available
    return is_available()


def _resolve_whisper_api_key(settings) -> str:
    """Read Whisper API key from Docker secret or WHISPER_API_KEY env var."""
    return settings.resolve_provider_key("whisper")


def _make_markitdown(cfg: dict, data_dir: str | None = None, settings=None):
    """Build a MarkItDown instance, registering the audio converter when enabled."""
    from markitdown import MarkItDown
    md = MarkItDown()
    if cfg.get("audio_enabled", False):
        provider = cfg.get("audio_provider", "local")
        if provider == "remote":
            api_base = cfg.get("audio_api_base", "").strip()
            if api_base:
                from app.plugins.converter.audio import make_markitdown_converter
                api_key = _resolve_whisper_api_key(settings) if settings else ""
                converter = make_markitdown_converter(
                    provider="remote", api_base=api_base, api_key=api_key,
                )
                if converter:
                    md.register_converter(converter)
        elif _has_audio_support():
            from app.plugins.converter.audio import make_markitdown_converter
            model_size = cfg.get("audio_model", "small")
            converter = make_markitdown_converter(
                model_size=model_size, data_dir=data_dir, provider="local",
            )
            if converter:
                md.register_converter(converter)
    return md


def _convert_file(source: Path, dest: Path, md=None) -> str | None:
    """Convert a single file to markdown. Returns error message or None on success."""
    if md is None:
        from markitdown import MarkItDown
        md = MarkItDown()
    try:
        result = md.convert_local(source)
        if result.text_content:
            dest.write_text(result.text_content, encoding="utf-8")
            return None
        return f"No content extracted from {source.name}"
    except Exception as e:
        return f"Conversion failed: {e}"


# -- Background audio model install state --

_audio_install_status: dict = {"running": False, "progress": 0.0, "message": "", "result": ""}
_audio_install_lock = threading.Lock()


# -- Background conversion state --

_conversion_status: dict = {
    "running": False,
    "cancel": threading.Event(),
    "progress": 0.0,
    "message": "",
    "result": "",
    "files_done": 0,
    "files_total": 0,
    "errors": 0,
}
_conversion_lock = threading.Lock()


def _bg_convert(source_dir: str, dest_dir: str, extensions: set[str], md=None):
    """Run batch conversion in a background thread."""
    src = Path(source_dir)
    dst = Path(dest_dir)
    dst.mkdir(parents=True, exist_ok=True)

    files = [
        f for f in sorted(src.rglob("*"))
        if f.is_file() and f.suffix.lower() in extensions
    ]
    total = len(files)

    with _conversion_lock:
        _conversion_status["files_total"] = total
        _conversion_status["files_done"] = 0
        _conversion_status["errors"] = 0

    if total == 0:
        with _conversion_lock:
            _conversion_status["running"] = False
            _conversion_status["progress"] = 1.0
            _conversion_status["message"] = "Done"
            _conversion_status["result"] = "No convertible files found"
        return

    converted = 0
    errors = 0
    for i, f in enumerate(files):
        if _conversion_status["cancel"].is_set():
            with _conversion_lock:
                _conversion_status["message"] = "Cancelled"
                _conversion_status["result"] = f"Cancelled after {i}/{total} files ({converted} converted, {errors} errors)"
            break

        with _conversion_lock:
            _conversion_status["progress"] = i / max(total, 1)
            _conversion_status["message"] = f"Converting {f.name}..."
            _conversion_status["files_done"] = i

        relative = f.relative_to(src)
        dest_file = dst / relative.with_suffix(".md")
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        err = _convert_file(f, dest_file, md=md)
        if err:
            logger.warning("Conversion failed for %s: %s", f.name, err)
            errors += 1
        else:
            converted += 1

    with _conversion_lock:
        _conversion_status["progress"] = 1.0
        _conversion_status["files_done"] = total
        _conversion_status["errors"] = errors
        if not _conversion_status["cancel"].is_set():
            _conversion_status["message"] = "Done"
            _conversion_status["result"] = (
                f"Converted {converted}/{total} files to {dest_dir}"
                + (f" ({errors} errors)" if errors else "")
            )
        _conversion_status["running"] = False


# -- Endpoints --


class ConvertUrlRequest(BaseModel):
    url: str = Field(..., min_length=1, description="URL to convert (supports YouTube, web pages, and any URL markitdown handles)")


@router.post("/url")
@limiter.limit(HEAVY)
def convert_url(
    request: Request,
    req: ConvertUrlRequest,
    settings: Settings = Depends(get_settings),
):
    """Convert a URL to markdown. Requires web sub-converter to be enabled."""
    from app.security.validation import validate_api_base

    cfg = _plugin_config(settings)
    if not cfg.get("web_enabled", True):
        raise HTTPException(503, "Web/URL conversion is disabled. Enable 'web_enabled' in converter plugin settings.")

    try:
        validate_api_base(req.url)
    except ValueError as exc:
        raise HTTPException(400, f"URL not allowed: {exc}") from exc

    try:
        result = _make_markitdown(cfg).convert(req.url)
    except Exception as exc:
        raise HTTPException(400, f"Conversion failed: {exc}") from exc

    if not result.text_content:
        raise HTTPException(422, "No content could be extracted from the URL")

    title = (result.title or "").strip()
    markdown = result.text_content
    if req.url not in markdown:
        markdown = f"**Source:** {req.url}\n\n" + markdown

    return {
        "markdown": markdown,
        "title": title,
        "transcript_support": _has_transcript_support(),
    }


@router.post("/upload")
@limiter.limit(HEAVY)
async def convert_upload(
    request: Request,
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
):
    """Convert an uploaded file to markdown. Only formats whose sub-converter is enabled are accepted."""
    suffix = Path(file.filename or "upload").suffix.lower() or ".bin"
    cfg = _plugin_config(settings)
    fmt_name = _EXT_TO_FORMAT.get(suffix)
    if fmt_name:
        fmt_info = ALL_FORMATS[fmt_name]
        sub = fmt_info["subconverter"]
        if not cfg.get(f"{sub}_enabled", True):
            raise HTTPException(
                503,
                f"{fmt_info['label']} conversion is disabled. "
                f"Enable '{sub}_enabled' in converter plugin settings.",
            )

    fd, tmp = tempfile.mkstemp(suffix=suffix)
    try:
        os.close(fd)
        with open(tmp, "wb") as f:
            shutil.copyfileobj(file.file, f)
        result = _make_markitdown(cfg, settings.data_directory, settings).convert_local(Path(tmp))
    except Exception as exc:
        logger.error("converter/upload failed for %s: %s", file.filename, exc)
        raise HTTPException(400, f"Conversion failed: {exc}") from exc
    finally:
        Path(tmp).unlink(missing_ok=True)

    if not result.text_content:
        raise HTTPException(422, "No content could be extracted from the file")

    return {
        "markdown": result.text_content,
        "filename": file.filename,
    }


@router.get("/formats")
@limiter.limit(STANDARD)
def list_formats(request: Request, settings: Settings = Depends(get_settings)):
    """List all known formats with availability status, plus enabled subset."""
    enabled = _enabled_formats(settings)
    cfg = _plugin_config(settings)
    subconverter_enabled = {
        sub: cfg.get(f"{sub}_enabled", True)
        for sub in _FORMATS_BY_SUBCONVERTER
    }
    return {
        "formats": {
            name: {
                "label": info["label"],
                "extensions": info["extensions"],
                "subconverter": info["subconverter"],
                "available": name in enabled,
            }
            for name, info in ALL_FORMATS.items()
        },
        "subconverters": subconverter_enabled,
        "web_enabled": cfg.get("web_enabled", True),
        "transcript_support": _has_transcript_support(),
        "audio_support": _has_audio_support(),
    }


class ConvertRequest(BaseModel):
    source_dir: str = Field(..., min_length=1)
    dest_dir: str = Field(..., min_length=1)
    formats: list[str] | None = Field(None, description="Limit to specific formats. Null = all enabled formats.")


@router.post("/convert")
@limiter.limit(HEAVY)
def start_conversion(
    request: Request,
    req: ConvertRequest,
    settings: Settings = Depends(get_settings),
):
    """Start batch conversion of files in a directory to markdown."""
    src = Path(req.source_dir)
    if not src.is_dir():
        raise HTTPException(400, f"Source directory not found: {req.source_dir}")

    dst = Path(req.dest_dir)
    resolved_dst = str(dst.resolve())
    in_source = any(
        resolved_dst == str(Path(s).resolve())
        or resolved_dst.startswith(str(Path(s).resolve()) + "/")
        for s in settings.sources
    )
    if not in_source:
        if not dst.exists():
            try:
                dst.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise HTTPException(400, f"Cannot create destination: {e}") from e

    enabled = _enabled_formats(settings)

    if req.formats:
        extensions: set[str] = set()
        for fmt_name in req.formats:
            fmt = enabled.get(fmt_name)
            if fmt:
                extensions.update(fmt["extensions"])
        if not extensions:
            raise HTTPException(400, f"No enabled formats in: {req.formats}")
    else:
        extensions = {ext for info in enabled.values() for ext in info["extensions"]}

    with _conversion_lock:
        if _conversion_status["running"]:
            raise HTTPException(409, "Conversion already in progress")
        _conversion_status["running"] = True
        _conversion_status["cancel"].clear()
        _conversion_status["progress"] = 0.0
        _conversion_status["message"] = "Starting conversion..."
        _conversion_status["result"] = ""
        _conversion_status["files_done"] = 0
        _conversion_status["files_total"] = 0
        _conversion_status["errors"] = 0

    md = _make_markitdown(_plugin_config(settings), settings.data_directory, settings)
    threading.Thread(
        target=_bg_convert,
        args=(req.source_dir, req.dest_dir, extensions),
        kwargs={"md": md},
        daemon=True,
    ).start()
    return {"status": "started"}


@router.post("/ingest")
@limiter.limit(HEAVY)
async def ingest_file(
    request: Request,
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
    """Convert a file and ingest it directly into the main knowledge base.

    Writes the converted .md to the first writable source directory and
    indexes it immediately. The file appears in the Files tab after import.
    """
    writable = settings.writable_sources
    if not writable:
        raise HTTPException(
            status_code=422,
            detail="No writable source directories configured.",
        )

    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix == ".md":
        raise HTTPException(
            status_code=400,
            detail="Markdown files can be placed directly in a source directory — no conversion needed.",
        )

    fmt_name = _EXT_TO_FORMAT.get(suffix)
    if fmt_name:
        fmt_info = ALL_FORMATS[fmt_name]
        sub = fmt_info["subconverter"]
        cfg = _plugin_config(settings)
        if not cfg.get(f"{sub}_enabled", True):
            raise HTTPException(
                status_code=503,
                detail=f"{fmt_info['label']} conversion is disabled. Enable '{sub}_enabled' in converter plugin settings.",
            )

    stem = Path(file.filename or "upload").stem
    dest_dir = Path(writable[0])

    cfg = _plugin_config(settings)

    # Guard: audio files require transcription to be enabled and configured
    if suffix in {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"}:
        if not cfg.get("audio_enabled", False):
            raise HTTPException(
                status_code=503,
                detail="Audio transcription is disabled. Enable it in Settings → File Converter.",
            )
        audio_provider = cfg.get("audio_provider", "local")
        if audio_provider == "remote":
            if not cfg.get("audio_api_base", "").strip():
                raise HTTPException(
                    status_code=503,
                    detail="Remote audio transcription requires an API base URL. Configure it in Settings → File Converter.",
                )
        else:
            from app.plugins.converter.audio import is_model_installed
            model_size = cfg.get("audio_model", "small")
            if not is_model_installed(model_size, settings.data_directory):
                raise HTTPException(
                    status_code=503,
                    detail=(
                        f"Whisper model '{model_size}' is not installed. "
                        "Download it in Settings → File Converter."
                    ),
                )

    fd, tmp = tempfile.mkstemp(suffix=suffix)
    try:
        os.close(fd)
        with open(tmp, "wb") as f:
            shutil.copyfileobj(file.file, f)
        result = _make_markitdown(cfg, settings.data_directory, settings).convert_local(Path(tmp))
    except Exception as exc:
        logger.error("converter/ingest failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=400, detail=f"Conversion failed: {exc}") from exc
    finally:
        Path(tmp).unlink(missing_ok=True)

    if not result.text_content:
        raise HTTPException(status_code=422, detail="No content could be extracted from the file.")

    dest_path = dest_dir / f"{stem}.md"
    counter = 1
    while dest_path.exists():
        dest_path = dest_dir / f"{stem}_{counter}.md"
        counter += 1

    dest_path.write_text(result.text_content, encoding="utf-8")
    path_str = str(dest_path)

    try:
        reindex_file(path_str, settings, store, tracking)
    except ReindexError as e:
        logger.warning("Ingest succeeded but indexing failed for %s: %s", path_str, e)

    event_bus.publish(IndexEvent(type="file_imported", path=path_str, filename=dest_path.name))
    return {"status": "ok", "path": path_str, "filename": dest_path.name}


@router.post("/cancel")
@limiter.limit(STANDARD)
def cancel_conversion(request: Request):
    """Cancel a running conversion."""
    _conversion_status["cancel"].set()
    return {"status": "cancelling"}


@router.get("/status")
@limiter.limit(STANDARD)
def conversion_status(request: Request):
    """Return current conversion progress."""
    with _conversion_lock:
        return {
            "running": _conversion_status["running"],
            "progress": _conversion_status["progress"],
            "message": _conversion_status["message"],
            "result": _conversion_status["result"],
            "files_done": _conversion_status["files_done"],
            "files_total": _conversion_status["files_total"],
            "errors": _conversion_status["errors"],
        }


# -- Audio model management endpoints --


class _AudioModelRequest(BaseModel):
    model_size: str


@router.get("/audio/models")
@limiter.limit(STANDARD)
def list_audio_models(request: Request, settings: Settings = Depends(get_settings)):
    """List available Whisper models with installation status."""
    from app.plugins.converter.audio import WHISPER_MODELS, is_model_installed
    cfg = _plugin_config(settings)
    active = cfg.get("audio_model", "small")
    provider = cfg.get("audio_provider", "local")
    return {
        "models": [
            {
                "model_size": size,
                "label": info["label"],
                "size": info["size"],
                "installed": is_model_installed(size, settings.data_directory),
                "active": size == active,
            }
            for size, info in WHISPER_MODELS.items()
        ],
        "audio_support": _has_audio_support(),
        "active_model": active,
        "provider": provider,
    }


def _bg_audio_install(model_size: str, data_dir: str) -> None:
    """Download a Whisper model in a background thread."""
    from app.plugins.converter.audio import download_model

    def on_progress(frac: float, msg: str) -> None:
        with _audio_install_lock:
            _audio_install_status["progress"] = frac
            _audio_install_status["message"] = msg

    try:
        download_model(model_size, data_dir, progress=on_progress)
        with _audio_install_lock:
            _audio_install_status["result"] = f"Installed faster-whisper-{model_size}"
    except Exception as exc:
        logger.error("Whisper model install failed (%s): %s", model_size, exc)
        with _audio_install_lock:
            _audio_install_status["result"] = f"Error: {exc}"
    finally:
        with _audio_install_lock:
            _audio_install_status["running"] = False


@router.post("/audio/install")
@limiter.limit(HEAVY)
def install_audio_model(
    request: Request,
    req: _AudioModelRequest,
    settings: Settings = Depends(get_settings),
):
    """Download a Whisper model in the background."""
    from app.plugins.converter.audio import WHISPER_MODELS, is_model_installed
    if req.model_size not in WHISPER_MODELS:
        raise HTTPException(400, f"Unknown model size: {req.model_size}")
    if is_model_installed(req.model_size, settings.data_directory):
        return {"status": "already_installed"}
    with _audio_install_lock:
        if _audio_install_status["running"]:
            raise HTTPException(409, "A model install is already in progress")
        _audio_install_status["running"] = True
        _audio_install_status["progress"] = 0.0
        _audio_install_status["message"] = f"Starting download of faster-whisper-{req.model_size}..."
        _audio_install_status["result"] = ""
    threading.Thread(
        target=_bg_audio_install,
        args=(req.model_size, settings.data_directory),
        daemon=True,
    ).start()
    return {"status": "installing"}


@router.get("/audio/status")
@limiter.limit(STANDARD)
def audio_install_status(request: Request):
    """Return current Whisper model install progress."""
    with _audio_install_lock:
        return dict(_audio_install_status)


@router.post("/audio/uninstall")
@limiter.limit(STANDARD)
def uninstall_audio_model(
    request: Request,
    req: _AudioModelRequest,
    settings: Settings = Depends(get_settings),
):
    """Remove downloaded Whisper model weights."""
    from app.plugins.converter.audio import WHISPER_MODELS, uninstall_model
    if req.model_size not in WHISPER_MODELS:
        raise HTTPException(400, f"Unknown model size: {req.model_size}")
    with _audio_install_lock:
        if _audio_install_status["running"]:
            raise HTTPException(409, "An install is in progress")
    removed = uninstall_model(req.model_size, settings.data_directory)
    return {"status": "removed" if removed else "not_installed"}
