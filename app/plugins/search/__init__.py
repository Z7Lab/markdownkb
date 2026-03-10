"""Search plugin — search with history, summarize, and query enhancement."""

from app.plugins.search.router import router

FEATURE_FLAG = "search"

__all__ = ["FEATURE_FLAG", "router"]
