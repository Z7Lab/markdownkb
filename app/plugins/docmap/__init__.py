"""Document map plugin — document similarity visualization."""

from app.plugins.docmap.router import (
    router,
    start_invalidation_thread,
    stop_invalidation_thread,
)

FEATURE_FLAG = "docmap"


def on_startup(app) -> None:
    """Start the cache invalidation worker thread."""
    start_invalidation_thread()


def on_shutdown(app) -> None:
    """Stop the cache invalidation worker thread."""
    stop_invalidation_thread()


__all__ = ["FEATURE_FLAG", "router", "on_startup", "on_shutdown"]
