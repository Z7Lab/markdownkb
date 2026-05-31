"""Converter endpoints — batch convert documents to markdown via markitdown."""

import logging
import os
import re
import shutil
import tempfile
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
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

# Aggregation layer for content ingestion. Mounted alongside the converter
# router (see __init__.py) but exposed under /api/v1/import so future surfaces
# can discover available import methods without knowing about the converter.
import_router = APIRouter(prefix="/api/v1/import", tags=["import"])

_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"}

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


def _audio_capability(settings: Settings) -> dict:
    """Resolve whether audio transcription is actually usable right now.

    Returns a dict with ``available`` plus the ``provider``, ``model_ready``
    state and a human ``reason`` when unavailable. Shared by ingest validation
    and the capabilities endpoint so both agree on what "ready" means.
    """
    cfg = _plugin_config(settings)
    enabled = cfg.get("audio_enabled", False)
    provider = cfg.get("audio_provider", "local")
    model = cfg.get("audio_model", "small")

    if not enabled:
        return {"available": False, "provider": provider, "model": model,
                "model_ready": False, "reason": "Audio transcription is disabled"}

    if provider == "remote":
        if not cfg.get("audio_api_base", "").strip():
            return {"available": False, "provider": provider, "model": model,
                    "model_ready": False,
                    "reason": "Remote transcription needs an API base URL"}
        return {"available": True, "provider": provider, "model": model,
                "model_ready": True, "reason": None}

    # Local provider
    if not _has_audio_support():
        return {"available": False, "provider": provider, "model": model,
                "model_ready": False,
                "reason": "faster-whisper is not installed (use the full image)"}
    from app.plugins.converter.audio import is_model_installed
    if not is_model_installed(model, settings.data_directory):
        return {"available": False, "provider": provider, "model": model,
                "model_ready": False,
                "reason": f"Whisper model '{model}' is not downloaded"}
    return {"available": True, "provider": provider, "model": model,
            "model_ready": True, "reason": None}


def _resolve_destination(settings: Settings, destination: str) -> Path:
    """Resolve and validate an ingest destination source directory.

    ``destination`` may be empty (use the first writable source) or an explicit
    writable source path. Raises HTTPException on an invalid choice.
    """
    writable = settings.writable_sources
    if not writable:
        raise HTTPException(
            status_code=422,
            detail="No writable source directories configured.",
        )
    if not destination:
        return Path(writable[0])
    resolved = str(Path(destination).resolve())
    for w in writable:
        if str(Path(w).resolve()) == resolved:
            return Path(w)
    raise HTTPException(
        status_code=400,
        detail=f"'{destination}' is not a writable source directory.",
    )


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


# -- Background ingest state (per-job, keyed by job id) --

_ingest_jobs: dict[str, dict] = {}
_ingest_lock = threading.Lock()
_INGEST_JOB_LIMIT = 50


def _new_ingest_job() -> str:
    """Create a job record and return its id, pruning old finished jobs."""
    job_id = uuid.uuid4().hex[:12]
    with _ingest_lock:
        # Prune finished jobs once we exceed the cap (dict preserves order).
        if len(_ingest_jobs) >= _INGEST_JOB_LIMIT:
            for stale_id in [
                jid for jid, j in list(_ingest_jobs.items()) if not j["running"]
            ][: len(_ingest_jobs) - _INGEST_JOB_LIMIT + 1]:
                _ingest_jobs.pop(stale_id, None)
        _ingest_jobs[job_id] = {
            "running": True,
            "progress": 0.0,
            "message": "Queued…",
            "result": None,
            "error": None,
        }
    return job_id


def _update_ingest_job(job_id: str, **fields) -> None:
    with _ingest_lock:
        job = _ingest_jobs.get(job_id)
        if job is not None:
            job.update(fields)


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


def _slugify_stem(text: str, fallback: str = "imported") -> str:
    """Turn arbitrary text into a safe markdown filename stem."""
    s = re.sub(r"[^\w\s-]", "", text.strip().lower())
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s[:60] or fallback


def _bg_ingest(
    job_id: str,
    *,
    kind: str,
    payload: str,
    suffix: str,
    base_name: str,
    dest_dir: Path,
    cfg: dict,
    settings: Settings,
    store: VectorStore,
    tracking: TrackingDB,
) -> None:
    """Convert, write and index a single item in the background.

    ``kind`` is one of ``"file"`` (convert via markitdown), ``"md"`` (raw
    markdown — write as-is) or ``"url"`` (fetch + convert). For ``file``/``md``
    the *payload* is a temp file path; for ``url`` it is the URL string.
    """
    try:
        if kind == "md":
            text = Path(payload).read_text(encoding="utf-8", errors="replace")
            Path(payload).unlink(missing_ok=True)
        elif kind == "url":
            _update_ingest_job(job_id, message=f"Fetching {payload}…", progress=0.3)
            result = _make_markitdown(cfg, settings.data_directory, settings).convert(payload)
            text = result.text_content or ""
            if text and payload not in text:
                text = f"**Source:** {payload}\n\n" + text
            title = (result.title or "").strip()
            if title:
                base_name = _slugify_stem(title, base_name)
        elif suffix in _AUDIO_EXTENSIONS and cfg.get("audio_provider", "local") == "local":
            # Local audio: transcribe directly so we get segment-level progress.
            from app.plugins.converter.audio import transcribe_path

            def _cb(frac: float, msg: str) -> None:
                _update_ingest_job(job_id, progress=frac, message=msg)

            transcript = transcribe_path(
                Path(payload), cfg.get("audio_model", "small"),
                settings.data_directory, progress=_cb,
            )
            text = (
                f"### Audio Transcript\n\n{transcript}"
                if transcript.strip()
                else "### Audio Transcript\n\n*(no speech detected)*"
            )
            Path(payload).unlink(missing_ok=True)
        else:
            _update_ingest_job(job_id, message=f"Converting {base_name}{suffix}…", progress=0.4)
            result = _make_markitdown(cfg, settings.data_directory, settings).convert_local(Path(payload))
            text = result.text_content or ""
            Path(payload).unlink(missing_ok=True)

        if not text.strip():
            _update_ingest_job(
                job_id, running=False, progress=1.0,
                error="No content could be extracted.",
            )
            return

        _update_ingest_job(job_id, message="Writing to knowledge base…", progress=0.95)
        dest_path = dest_dir / f"{base_name}.md"
        counter = 1
        while dest_path.exists():
            dest_path = dest_dir / f"{base_name}_{counter}.md"
            counter += 1
        dest_path.write_text(text, encoding="utf-8")
        path_str = str(dest_path)

        try:
            reindex_file(path_str, settings, store, tracking)
        except ReindexError as e:
            logger.warning("Ingest wrote %s but indexing failed: %s", path_str, e)

        event_bus.publish(IndexEvent(type="file_imported", path=path_str, filename=dest_path.name))
        _update_ingest_job(
            job_id, running=False, progress=1.0, message="Done",
            result={"path": path_str, "filename": dest_path.name},
        )
    except Exception as exc:
        logger.error("Ingest job %s failed: %s", job_id, exc)
        if kind != "url":
            Path(payload).unlink(missing_ok=True)
        _update_ingest_job(job_id, running=False, error=f"Import failed: {exc}")


@router.post("/ingest")
@limiter.limit(HEAVY)
async def ingest_file(
    request: Request,
    file: UploadFile | None = File(None),
    url: str = Form(""),
    destination: str = Form(""),
    settings: Settings = Depends(get_settings),
    tracking: TrackingDB = Depends(get_tracking),
    store: VectorStore = Depends(get_store),
):
    """Convert content and ingest it into the main knowledge base (async).

    Accepts either an uploaded *file* or a *url*, plus an optional *destination*
    (a writable source directory; defaults to the first one). Conversion runs in
    a background thread — the response returns a job id immediately. Poll
    ``GET /api/v1/converter/ingest/status/{job_id}`` for progress and the result.
    """
    dest_dir = _resolve_destination(settings, destination)
    cfg = _plugin_config(settings)
    url = url.strip()

    if file is None and not url:
        raise HTTPException(400, "Provide a file or a url to ingest.")
    if file is not None and url:
        raise HTTPException(400, "Provide either a file or a url, not both.")

    # -- URL ingest --
    if url:
        if not cfg.get("web_enabled", True):
            raise HTTPException(503, "Web/URL conversion is disabled. Enable 'web_enabled' in converter plugin settings.")
        from app.security.validation import validate_api_base
        try:
            validate_api_base(url)
        except ValueError as exc:
            raise HTTPException(400, f"URL not allowed: {exc}") from exc
        job_id = _new_ingest_job()
        threading.Thread(
            target=_bg_ingest,
            args=(job_id,),
            kwargs=dict(
                kind="url", payload=url, suffix="",
                base_name=_slugify_stem(url.split("//")[-1], "clipped"),
                dest_dir=dest_dir, cfg=cfg, settings=settings, store=store, tracking=tracking,
            ),
            daemon=True,
        ).start()
        return {"job_id": job_id, "status": "started"}

    # -- File ingest --
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    base_name = _slugify_stem(Path(filename).stem, "imported")

    if suffix == ".md":
        kind = "md"
    else:
        kind = "file"
        fmt_name = _EXT_TO_FORMAT.get(suffix)
        if fmt_name:
            fmt_info = ALL_FORMATS[fmt_name]
            sub = fmt_info["subconverter"]
            if not cfg.get(f"{sub}_enabled", True):
                raise HTTPException(
                    503,
                    f"{fmt_info['label']} conversion is disabled. Enable '{sub}_enabled' in converter plugin settings.",
                )
        if suffix in _AUDIO_EXTENSIONS:
            audio = _audio_capability(settings)
            if not audio["available"]:
                raise HTTPException(503, audio["reason"] or "Audio transcription is unavailable.")

    # Persist the upload synchronously — the UploadFile stream closes once we
    # return, so the background worker reads from this temp file instead.
    fd, tmp = tempfile.mkstemp(suffix=suffix or ".bin")
    os.close(fd)
    with open(tmp, "wb") as fh:
        shutil.copyfileobj(file.file, fh)

    job_id = _new_ingest_job()
    threading.Thread(
        target=_bg_ingest,
        args=(job_id,),
        kwargs=dict(
            kind=kind, payload=tmp, suffix=suffix, base_name=base_name,
            dest_dir=dest_dir, cfg=cfg, settings=settings, store=store, tracking=tracking,
        ),
        daemon=True,
    ).start()
    return {"job_id": job_id, "status": "started"}


@router.get("/ingest/status/{job_id}")
@limiter.limit(STANDARD)
def ingest_status(request: Request, job_id: str):
    """Return progress/result for an async ingest job."""
    with _ingest_lock:
        job = _ingest_jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "Unknown ingest job")
        return dict(job)


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


class _AudioTestRemoteRequest(BaseModel):
    api_base: str
    api_key: str = ""


@router.post("/audio/test-remote")
@limiter.limit(STANDARD)
def test_remote_audio_endpoint(
    request: Request,
    req: _AudioTestRemoteRequest,
):
    """Test connectivity to a remote OpenAI-compatible audio transcription API.

    Sends a lightweight GET to ``{api_base}/v1/models`` to check reachability
    and authentication without uploading any audio data.
    """
    import httpx
    from app.security.validation import validate_api_base

    try:
        validate_api_base(req.api_base)
    except ValueError as exc:
        raise HTTPException(400, f"URL not allowed: {exc}") from exc

    base = req.api_base.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"

    headers: dict[str, str] = {}
    if req.api_key:
        headers["Authorization"] = f"Bearer {req.api_key}"

    try:
        resp = httpx.get(f"{base}/models", headers=headers, timeout=10)
        if resp.status_code == 200:
            return {"ok": True, "message": "Connection successful"}
        elif resp.status_code == 401:
            return {"ok": False, "message": "Authentication failed — check your API key"}
        elif resp.status_code == 403:
            return {"ok": False, "message": "Forbidden — check your API key permissions"}
        else:
            return {"ok": True, "message": f"Server reachable (HTTP {resp.status_code})"}
    except httpx.ConnectError:
        return {"ok": False, "message": f"Cannot connect to {req.api_base}"}
    except httpx.TimeoutException:
        return {"ok": False, "message": "Connection timed out"}
    except Exception as exc:
        return {"ok": False, "message": f"Error: {exc}"}


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


# -- Import capabilities aggregation --


@import_router.get("/capabilities")
@limiter.limit(STANDARD)
def import_capabilities(request: Request, settings: Settings = Depends(get_settings)):
    """Aggregate every available content-import method for the main KB.

    Single source of truth for the frontend: each consumer of the shared
    ingestion UI renders exactly the methods returned here. Availability and the
    reason for unavailability are decided entirely on the backend so no
    capability logic lives in the frontend.
    """
    cfg = _plugin_config(settings)
    enabled_fmts = _enabled_formats(settings)
    audio = _audio_capability(settings)

    # File formats: a format is genuinely available only when its sub-converter
    # is enabled AND — for audio — transcription is actually usable right now.
    formats: list[dict] = []
    accepted: list[str] = [".md", ".markdown"]
    for name, info in ALL_FORMATS.items():
        is_audio = info["subconverter"] == "audio"
        available = (name in enabled_fmts) and (audio["available"] if is_audio else True)
        formats.append({
            "label": info["label"],
            "extensions": info["extensions"],
            "available": available,
        })
        if available:
            accepted.extend(info["extensions"])

    web_enabled = cfg.get("web_enabled", True)
    write_api_on = settings.plugin_enabled("write_api")
    save_document_on = settings.mcp_enabled("save_document")

    def _create_reason() -> str | None:
        if not write_api_on:
            return "Enable the Write API plugin to create documents"
        if not save_document_on:
            return "Enable the 'save_document' MCP flag to create documents"
        return None

    methods = [
        {
            "id": "file_upload",
            "label": "Upload File",
            "available": len(enabled_fmts) > 0,
            "accept": ",".join(sorted(set(accepted))),
            "formats": formats,
            "reason": None if enabled_fmts else "No converter formats are enabled",
        },
        {
            "id": "url_clip",
            "label": "Web & YouTube",
            "available": web_enabled,
            "transcript_support": _has_transcript_support(),
            "reason": None if web_enabled else "Web/URL conversion is disabled",
        },
        {
            "id": "audio",
            "label": "Audio Transcription",
            "available": audio["available"],
            "provider": audio["provider"],
            "model": audio["model"],
            "model_ready": audio["model_ready"],
            "reason": audio["reason"],
        },
        {
            "id": "create_markdown",
            "label": "Create Markdown",
            "available": write_api_on and save_document_on,
            "reason": _create_reason(),
        },
    ]
    return {"methods": methods}
