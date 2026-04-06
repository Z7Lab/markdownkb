"""Knowledge graph plugin — entity extraction and typed relationships."""

import logging

from app.plugins.knowledge_graph.router import router

logger = logging.getLogger(__name__)

FEATURE_FLAG = "knowledge_graph"


def on_startup(app) -> None:
    """Initialize KnowledgeGraphDB on plugin startup."""
    from app.storage.knowledgegraph import KnowledgeGraphDB

    settings = app.state.settings
    kgdb = KnowledgeGraphDB(settings.data_directory)
    app.state.kgdb = kgdb
    logger.info("KnowledgeGraphDB initialized")


def on_shutdown(app) -> None:
    """Close KnowledgeGraphDB on plugin shutdown."""
    kgdb = getattr(app.state, "kgdb", None)
    if kgdb:
        kgdb.close()


__all__ = ["FEATURE_FLAG", "router", "on_startup", "on_shutdown"]
