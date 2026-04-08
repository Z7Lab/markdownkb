"""Tags plugin — tag storage, CRUD, auto-tagging, and optional AI generation."""

import logging

from app.plugins.tags.router import router

logger = logging.getLogger(__name__)

FEATURE_FLAG = "tags"

__all__ = ["FEATURE_FLAG", "router", "on_startup", "on_shutdown"]


def on_startup(app) -> None:
    """Initialize TagDB, migrate data from TrackingDB, register hooks."""
    from app import tag_utils
    from app.plugins.tags.tagdb import TagDB

    settings = app.state.settings
    tagdb = TagDB(settings.data_directory)
    app.state.tagdb = tagdb

    # Sync tags from ChromaDB chunk metadata into TagDB.
    # Frontmatter tags are stored in chunk metadata during indexing but
    # only written to TagDB via notify_tags_extracted — files indexed
    # before the tags plugin was enabled are missing. This backfills them.
    try:
        store = app.state.store
        all_meta = store.get_all_metadatas()
        existing_paths = tagdb.get_all_paths()
        synced = 0
        seen: dict[str, set[str]] = {}
        for meta in all_meta:
            path = meta.get("source_path", "")
            raw_tags = meta.get("tags", "")
            if not path or not raw_tags:
                continue
            if isinstance(raw_tags, list):
                tags = {t.strip() for t in raw_tags if t.strip()}
            else:
                tags = {t.strip() for t in raw_tags.split(",") if t.strip()}
            if tags:
                seen.setdefault(path, set()).update(tags)
        for path, tags in seen.items():
            if path not in existing_paths:
                tagdb.update_tags(path, ", ".join(sorted(tags)))
                synced += 1
        if synced:
            logger.info("Synced frontmatter tags for %d files from ChromaDB into TagDB", synced)

        # Prune TagDB entries for files no longer in ChromaDB
        indexed_paths = {meta.get("source_path", "") for meta in all_meta if meta.get("source_path")}
        stale = existing_paths - indexed_paths
        for path in stale:
            tagdb.remove_file(path)
        if stale:
            logger.info("Pruned %d stale tag entries (files no longer indexed)", len(stale))
    except Exception as e:
        logger.warning("Failed to sync tags from ChromaDB: %s", e)

    # Register hooks so core can resolve tags without importing this plugin
    tag_utils.register_resolver(tagdb.get_paths_for_tags)
    tag_utils.register_tag_lister(tagdb.get_all_tags)
    tag_utils.register_file_tags_lister(tagdb.get_all_file_tags)
    tag_utils.register_tags_hook(tagdb.update_tags)
    tag_utils.register_delete_hook(tagdb.remove_file)


def on_shutdown(app) -> None:
    """Close TagDB connection."""
    tagdb = getattr(app.state, "tagdb", None)
    if tagdb:
        tagdb.close()
