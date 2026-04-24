"""Tag resolution utilities — dispatcher pattern for plugin-provided tag services.

Core provides the interface; the tags plugin registers its implementation
at startup.  If no plugin registers, all functions degrade gracefully
(no filtering, empty tag lists, no-op hooks).
"""

from typing import Callable


# -- Plugin-registerable callbacks -------------------------------------------

_resolver: Callable[[set[str]], set[str]] | None = None
_tag_lister: Callable[[], list[str]] | None = None
_tags_hook: Callable[[str, str], None] | None = None
_file_tags_lister: Callable[[], list[dict]] | None = None
_delete_hook: Callable[[str], None] | None = None


def register_resolver(fn: Callable[[set[str]], set[str]]) -> None:
    """Register the function that maps a set of tags to matching file paths."""
    global _resolver
    _resolver = fn


def register_tag_lister(fn: Callable[[], list[str]]) -> None:
    """Register the function that returns all unique tags."""
    global _tag_lister
    _tag_lister = fn


def register_file_tags_lister(fn: Callable[[], list[dict]]) -> None:
    """Register the function that returns all (path, tags) rows."""
    global _file_tags_lister
    _file_tags_lister = fn


def register_tags_hook(fn: Callable[[str, str], None]) -> None:
    """Register the callback invoked when the indexer extracts tags from frontmatter."""
    global _tags_hook
    _tags_hook = fn


# -- Public API (called by core routers / indexer) ---------------------------

def resolve_tag_paths(
    scope_tags: list[str] | None,
    ad_hoc_tags: list[str] | None,
) -> set[str] | None:
    """Resolve scope tags + ad-hoc tags to a set of allowed file paths.

    Merges both tag sources with OR logic: a file matches if it has
    any of the specified tags.  Returns None if no tags are active
    or no resolver is registered (no-op = all files pass).
    """
    all_tags: set[str] = set()
    if scope_tags:
        all_tags.update(scope_tags)
    if ad_hoc_tags:
        all_tags.update(ad_hoc_tags)

    if not all_tags:
        return None

    if _resolver is None:
        return None

    return _resolver(all_tags)


def get_all_tags() -> list[str]:
    """Return sorted list of all unique tags.  Empty if no plugin registered."""
    if _tag_lister is None:
        return []
    return _tag_lister()


def get_all_file_tags() -> list[dict]:
    """Return all (path, tags) rows.  Empty if no plugin registered."""
    if _file_tags_lister is None:
        return []
    return _file_tags_lister()


def register_delete_hook(fn: Callable[[str], None]) -> None:
    """Register the callback invoked when a file is removed from the index."""
    global _delete_hook
    _delete_hook = fn


def notify_tags_extracted(path: str, tags: str) -> None:
    """Called by the indexer when tags are parsed from frontmatter.

    Delegates to the registered hook (TagDB.update_tags) if present.
    No-op if no tags plugin is active.
    """
    if _tags_hook and tags:
        _tags_hook(path, tags)


def notify_file_deleted(path: str) -> None:
    """Called when a file is removed from the index.

    Delegates to the registered hook (TagDB.remove_file) if present.
    No-op if no tags plugin is active.
    """
    if _delete_hook:
        _delete_hook(path)
