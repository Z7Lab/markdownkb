"""Converter endpoints — batch convert documents to markdown via markitdown."""

import logging
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_settings
from app.ratelimit import HEAVY, STANDARD, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/converter", tags=["converter"])

# Supported input formats and their file extensions
SUPPORTED_FORMATS = {
    "docx": {"extensions": [".docx"], "label": "Microsoft Word"},
    "pdf": {"extensions": [".pdf"], "label": "PDF"},
    "pptx": {"extensions": [".pptx"], "label": "PowerPoint"},
    "xlsx": {"extensions": [".xlsx"], "label": "Excel (xlsx)"},
    "xls": {"extensions": [".xls"], "label": "Excel (xls)"},
    "html": {"extensions": [".html", ".htm"], "label": "HTML"},
    "epub": {"extensions": [".epub"], "label": "EPUB"},
    "csv": {"extensions": [".csv"], "label": "CSV"},
    "txt": {"extensions": [".txt"], "label": "Plain Text"},
    "rst": {"extensions": [".rst"], "label": "reStructuredText"},
    "rtf": {"extensions": [".rtf"], "label": "Rich Text"},
    "odt": {"extensions": [".odt"], "label": "LibreOffice"},
    "ipynb": {"extensions": [".ipynb"], "label": "Jupyter Notebook"},
    "msg": {"extensions": [".msg"], "label": "Outlook Message"},
}

ALL_EXTENSIONS = {ext for fmt in SUPPORTED_FORMATS.values() for ext in fmt["extensions"]}


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
        md = MarkItDown()
        result = md.convert_local(source)
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

    # Discover convertible files
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

        # Preserve subdirectory structure
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
    url: str = Field(..., min_length=1, description="URL to convert to markdown (supports YouTube, web pages, and any URL markitdown handles)")


@router.post("/url")
@limiter.limit(HEAVY)
def convert_url(request: Request, req: ConvertUrlRequest):
    """Convert a URL to markdown. YouTube URLs extract title, description, and transcript (if youtube_transcript_api is installed)."""
    from markitdown import MarkItDown

    try:
        result = MarkItDown().convert(req.url)
    except Exception as exc:
        raise HTTPException(400, f"Conversion failed: {exc}") from exc

    if not result.text_content:
        raise HTTPException(422, "No content could be extracted from the URL")

    return {
        "markdown": result.text_content,
        "transcript_support": _has_transcript_support(),
    }


class ConvertRequest(BaseModel):
    source_dir: str = Field(..., min_length=1, description="Directory containing files to convert")
    dest_dir: str = Field(..., min_length=1, description="Destination directory for markdown output (must be a watched source or writable path)")
    formats: list[str] | None = Field(None, description="Limit to specific formats (e.g. ['docx', 'pdf']). Null = all supported.")


@router.get("/formats")
@limiter.limit(STANDARD)
def list_formats(request: Request):
    """List supported input formats."""
    return {
        "formats": {
            name: {
                "label": info["label"],
                "extensions": info["extensions"],
            }
            for name, info in SUPPORTED_FORMATS.items()
        },
    }


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
    # Validate destination is a watched source directory
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

    # Determine which extensions to convert
    if req.formats:
        extensions: set[str] = set()
        for fmt_name in req.formats:
            fmt = SUPPORTED_FORMATS.get(fmt_name)
            if fmt:
                extensions.update(fmt["extensions"])
        if not extensions:
            raise HTTPException(400, f"No recognized formats in: {req.formats}")
    else:
        extensions = ALL_EXTENSIONS

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
