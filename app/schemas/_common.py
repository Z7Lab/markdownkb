"""Shared validators and constants for request schemas."""

import re

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-.:]{1,128}$")
_MAX_ID_LIST = 50


def normalize_id_list(value):
    """Validator: accept list[str] or comma-separated str and return list[str].

    Enforces per-ID character/length limits and a maximum list length so
    pathological inputs can't slip past into downstream services.
    """
    if value is None or value == "":
        return None
    if isinstance(value, str):
        items = [p.strip() for p in value.split(",") if p.strip()]
    elif isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
    else:
        raise ValueError("IDs must be a list or comma-separated string")
    if not items:
        return None
    if len(items) > _MAX_ID_LIST:
        raise ValueError(f"Too many IDs (max {_MAX_ID_LIST})")
    for item in items:
        if not _ID_PATTERN.match(item):
            raise ValueError(f"Invalid ID format: {item[:32]!r}")
    return items
