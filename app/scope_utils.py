"""Scope resolution utilities — resolves scope IDs to folder/tag filters."""

from fnmatch import fnmatch

from fastapi import HTTPException

from app.storage.scopedb import ScopeDB


def parse_scope_ids(scope_ids) -> list[str] | None:
    """Normalize a scope/bucket ID input to a list.

    Accepts ``None``, a list (returned as-is if non-empty), or a
    comma-separated string. The request models in :mod:`app.schemas`
    already normalize to ``list[str]`` via a ``field_validator``; this
    helper remains so query-parameter code paths (e.g. docmap router) that
    still receive raw strings continue to work.
    """
    if not scope_ids:
        return None
    if isinstance(scope_ids, list):
        ids = [str(s).strip() for s in scope_ids if str(s).strip()]
        return ids or None
    ids = [s.strip() for s in str(scope_ids).split(",") if s.strip()]
    return ids or None


def resolve_scopes_raw(
    scope_ids: list[str] | None, scopedb: ScopeDB,
) -> tuple[list[str] | None, list[str] | None, list[str]]:
    """Resolve one or more scope IDs into merged (folders, tags, exclude_patterns).

    Returns (folders_or_None, tags_or_None, exclude_patterns).
    Raises ValueError if a scope ID is not found.
    """
    if not scope_ids:
        return None, None, []

    all_folders: list[str] = []
    all_tags: list[str] = []
    all_excludes: list[str] = []
    for sid in scope_ids:
        scope = scopedb.get(sid)
        if not scope:
            raise ValueError(f"Scope not found: {sid}")
        all_folders.extend(scope["folders"])
        all_tags.extend(scope["tags"])
        all_excludes.extend(scope.get("exclude_patterns", []))

    # Deduplicate while preserving order
    folders = list(dict.fromkeys(all_folders)) or None
    tags = list(dict.fromkeys(all_tags)) or None
    excludes = list(dict.fromkeys(all_excludes))
    return folders, tags, excludes


def resolve_scopes(
    scope_ids: list[str] | None, scopedb: ScopeDB,
) -> tuple[list[str] | None, list[str] | None, list[str]]:
    """Resolve one or more scope IDs into merged (folders, tags, exclude_patterns).

    Returns (folders_or_None, tags_or_None, exclude_patterns).
    Raises HTTPException(404) if a scope ID is not found.
    """
    try:
        return resolve_scopes_raw(scope_ids, scopedb)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


def apply_exclude_patterns(paths: set[str] | None, patterns: list[str]) -> set[str] | None:
    """Filter a set of paths by removing those matching any exclude pattern.

    Patterns use fnmatch glob syntax — matched against the full path and
    also against the basename. Examples:
      - ``agent-reviewed-*`` matches any file starting with agent-reviewed-
      - ``**/internal/**`` matches paths containing /internal/
      - ``*.tmp`` matches any .tmp file

    Returns None if input is None (no filtering active).
    """
    if paths is None or not patterns:
        return paths
    return {
        p for p in paths
        if not any(fnmatch(p, pat) or fnmatch(p.rsplit("/", 1)[-1], pat) for pat in patterns)
    }
