"""Shared utility functions for the mdkb API."""

import json
from pathlib import Path


def sse(event: str, data: dict) -> str:
    """Format a server-sent event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def short_title(message: str, limit: int = 80) -> str:
    """Derive a short thread title from the first user message."""
    text = message.strip().split("\n")[0]
    # Take first sentence if there's punctuation
    for ch in ".?!":
        idx = text.find(ch)
        if 0 < idx < limit:
            return text[: idx + 1]
    # Otherwise truncate at word boundary
    if len(text) <= limit:
        return text
    cut = text[:limit].rfind(" ")
    if cut > 20:
        return text[:cut] + "..."
    return text[:limit] + "..."


def parse_model(model_string: str) -> tuple[str, str]:
    """Parse 'provider/model' string into (provider_type, model_name).

    Returns provider_type as one of: 'anthropic', 'openai', 'ollama', or
    the raw prefix for other OpenAI-compatible providers.
    """
    if "/" in model_string:
        prefix, model_name = model_string.split("/", 1)
        return prefix.lower(), model_name
    return "openai", model_string


def get_path_size(path: Path) -> int:
    """Get total size of a file or directory in bytes.

    For SQLite database files, includes WAL and SHM files in the total.
    """
    if path.is_file():
        total = path.stat().st_size
        if path.suffix == '.db':
            wal_file = path.parent / f"{path.name}-wal"
            shm_file = path.parent / f"{path.name}-shm"
            if wal_file.exists():
                total += wal_file.stat().st_size
            if shm_file.exists():
                total += shm_file.stat().st_size
        return total
    if path.is_dir():
        return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
    return 0
