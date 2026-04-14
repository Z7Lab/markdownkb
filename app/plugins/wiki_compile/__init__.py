"""Wiki Compile plugin — Karpathy-style LLM-driven wiki ingestion."""

import logging

from app.plugins.wiki_compile.router import router

FEATURE_FLAG = "wiki_compile"

__all__ = ["FEATURE_FLAG", "router", "on_startup", "on_shutdown"]

logger = logging.getLogger(__name__)


def on_startup(app) -> None:
    """Initialize WikiDB and put it on app.state for router access."""
    from app.plugins.wiki_compile.wikidb import WikiDB

    settings = app.state.settings
    wikidb = WikiDB(settings.data_directory)
    app.state.wikidb = wikidb


def on_shutdown(app) -> None:
    """Close WikiDB connection."""
    wikidb = getattr(app.state, "wikidb", None)
    if wikidb:
        wikidb.close()
