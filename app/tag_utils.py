"""Tag resolution utilities — maps tags to file paths via tracking DB."""

from app.storage.trackingdb import TrackingDB


def resolve_tag_paths(
    scope_tags: list[str] | None,
    ad_hoc_tags: list[str] | None,
    tracking: TrackingDB,
) -> set[str] | None:
    """Resolve scope tags + ad-hoc tags to a set of allowed file paths.

    Merges both tag sources with OR logic: a file matches if it has
    any of the specified tags.  Returns None if no tags are active.
    """
    all_tags: set[str] = set()
    if scope_tags:
        all_tags.update(scope_tags)
    if ad_hoc_tags:
        all_tags.update(ad_hoc_tags)

    if not all_tags:
        return None

    return tracking.get_paths_for_tags(all_tags)


def get_all_tags(tracking: TrackingDB) -> list[str]:
    """Return sorted list of all unique tags from the tracking DB."""
    tags: set[str] = set()
    for f in tracking.get_all_files():
        tag_str = f.get("tags", "")
        if tag_str:
            for t in tag_str.split(","):
                t = t.strip()
                if t:
                    tags.add(t)
    return sorted(tags)


def get_files_for_tag(tag: str, tracking: TrackingDB) -> list[str]:
    """Return list of file paths that have the given tag."""
    paths: list[str] = []
    for f in tracking.get_all_files():
        file_tags = {t.strip() for t in f.get("tags", "").split(",") if t.strip()}
        if tag in file_tags:
            paths.append(f["path"])
    return paths
