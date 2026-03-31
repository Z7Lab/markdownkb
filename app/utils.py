"""Shared utility functions for the mdkb API."""

import ipaddress
import json
from pathlib import Path
from urllib.parse import urlparse


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


# IPs that must never be reached via user-supplied URLs
_BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),     # AWS/cloud metadata
    ipaddress.ip_network("100.100.100.0/24"),    # Alibaba metadata
    ipaddress.ip_network("fd00::/8"),             # ULA IPv6
    ipaddress.ip_network("fe80::/10"),            # Link-local IPv6
]

_BLOCKED_HOSTNAMES = frozenset({
    "metadata.google.internal",
    "metadata.goog",
})


def validate_api_base(url: str) -> str:
    """Validate an api_base URL is safe for outbound requests.

    Blocks non-HTTP schemes, cloud metadata endpoints, and
    obviously dangerous targets. Returns the URL unchanged if valid,
    raises ValueError otherwise.
    """
    if not url:
        return url

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"api_base must use http or https scheme, got '{parsed.scheme}'")

    hostname = (parsed.hostname or "").lower()

    if not hostname:
        raise ValueError("api_base has no hostname")

    if hostname in _BLOCKED_HOSTNAMES:
        raise ValueError(f"Requests to {hostname} are not allowed")

    # Check for cloud metadata IPs
    try:
        addr = ipaddress.ip_address(hostname)
        for network in _BLOCKED_IP_NETWORKS:
            if addr in network:
                raise ValueError(f"Requests to {hostname} are not allowed (blocked IP range)")
    except ValueError as e:
        if "not allowed" in str(e):
            raise
        # hostname is not an IP literal — that's fine

    return url


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
