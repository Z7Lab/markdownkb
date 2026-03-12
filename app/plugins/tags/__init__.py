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

    # One-time migration from TrackingDB file_metadata
    tracking = app.state.tracking
    if tagdb.is_empty():
        migrated = 0
        for f in tracking.get_all_files():
            tags = f.get("tags", "")
            if tags:
                tagdb.update_tags(f["path"], tags)
                migrated += 1
        if migrated:
            logger.info("Migrated tags for %d files from TrackingDB to TagDB", migrated)

    # Register hooks so core can resolve tags without importing this plugin
    tag_utils.register_resolver(tagdb.get_paths_for_tags)
    tag_utils.register_tag_lister(tagdb.get_all_tags)
    tag_utils.register_file_tags_lister(tagdb.get_all_file_tags)
    tag_utils.register_tags_hook(tagdb.update_tags)


def on_shutdown(app) -> None:
    """Close TagDB connection."""
    tagdb = getattr(app.state, "tagdb", None)
    if tagdb:
        tagdb.close()
