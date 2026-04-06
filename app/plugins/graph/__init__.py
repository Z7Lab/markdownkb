"""Knowledge graph plugin — document similarity + entity graph visualization."""

from app.plugins.graph.router import router

FEATURE_FLAG = "graph"


def on_startup(app):
    """Initialize KG database on plugin startup."""
    from app.storage.knowledgegraph import KnowledgeGraphDB
    settings = app.state.settings
    app.state.kgdb = KnowledgeGraphDB(settings.data_directory)


def on_shutdown(app):
    """Close KG database on plugin shutdown."""
    kgdb = getattr(app.state, "kgdb", None)
    if kgdb:
        kgdb.close()


__all__ = ["FEATURE_FLAG", "router", "on_startup", "on_shutdown"]
