"""Shared utility functions for the mdkb API."""

import json


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
