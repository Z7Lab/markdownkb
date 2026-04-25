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
from app.deps import get_settings
from app.ratelimit import HEAVY, STANDARD, limiter

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
    try:
        import youtube_transcript_api  # noqa: F401
        return True
    except ImportError:
        return False


def _convert_file(source: Path, dest: Path) -> str | None:
    """Convert a single file to markdown. Returns error message or None on success."""
    from markitdown import MarkItDown
    try:
        result = MarkItDown().convert_local(source)
        if result.text_content:
            dest.write_text(result.text_content, encoding="utf-8")
            return None
        return f"No content extracted from {source.name}"
    except Exception as e:
        return f"Conversion failed: {e}"


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


def _bg_convert(source_dir: str, dest_dir: str, extensions: set[str]):
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

        err = _convert_file(f, dest_file)
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
    from markitdown import MarkItDown

    cfg = _plugin_config(settings)
    if not cfg.get("web_enabled", True):
        raise HTTPException(503, "Web/URL conversion is disabled. Enable 'web_enabled' in converter plugin settings.")

    try:
        result = MarkItDown().convert(req.url)
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
    from markitdown import MarkItDown

    suffix = Path(file.filename or "upload").suffix.lower() or ".bin"
    fmt_name = _EXT_TO_FORMAT.get(suffix)
    if fmt_name:
        fmt_info = ALL_FORMATS[fmt_name]
        sub = fmt_info["subconverter"]
        cfg = _plugin_config(settings)
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
        result = MarkItDown().convert_local(Path(tmp))
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
    """List enabled input formats, grouped by sub-converter."""
    enabled = _enabled_formats(settings)
    cfg = _plugin_config(settings)
    return {
        "formats": {
            name: {
                "label": info["label"],
                "extensions": info["extensions"],
                "subconverter": info["subconverter"],
            }
            for name, info in enabled.items()
        },
        "subconverters": {
            sub: cfg.get(f"{sub}_enabled", True)
            for sub in _FORMATS_BY_SUBCONVERTER
        },
        "web_enabled": cfg.get("web_enabled", True),
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

    threading.Thread(
        target=_bg_convert,
        args=(req.source_dir, req.dest_dir, extensions),
        daemon=True,
    ).start()
    return {"status": "started"}


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
