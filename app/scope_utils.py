"""Scope resolution utilities — resolves scope IDs to folder/tag filters."""

from fastapi import HTTPException

from app.storage.scopedb import ScopeDB


def parse_scope_ids(scope_ids: str | None) -> list[str] | None:
    """Parse comma-separated scope_ids string into a list."""
    if not scope_ids:
        return None
    ids = [s.strip() for s in scope_ids.split(",") if s.strip()]
    return ids or None


def resolve_scopes_raw(
    scope_ids: list[str] | None, scopedb: ScopeDB,
) -> tuple[list[str] | None, list[str] | None]:
    """Resolve one or more scope IDs into merged (folders, tags).

    Returns (folders_or_None, tags_or_None).
    Raises ValueError if a scope ID is not found.
    """
    if not scope_ids:
        return None, None

    all_folders: list[str] = []
    all_tags: list[str] = []
    for sid in scope_ids:
        scope = scopedb.get(sid)
        if not scope:
            raise ValueError(f"Scope not found: {sid}")
        all_folders.extend(scope["folders"])
        all_tags.extend(scope["tags"])

    # Deduplicate while preserving order
    folders = list(dict.fromkeys(all_folders)) or None
    tags = list(dict.fromkeys(all_tags)) or None
    return folders, tags


def resolve_scopes(
    scope_ids: list[str] | None, scopedb: ScopeDB,
) -> tuple[list[str] | None, list[str] | None]:
    """Resolve one or more scope IDs into merged (folders, tags).

    Returns (folders_or_None, tags_or_None).
    Raises HTTPException(404) if a scope ID is not found.
    """
    try:
        return resolve_scopes_raw(scope_ids, scopedb)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
