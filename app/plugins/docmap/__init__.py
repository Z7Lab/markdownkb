"""Document map plugin — document similarity visualization."""

from app.plugins.docmap.router import router

FEATURE_FLAG = "docmap"

__all__ = ["FEATURE_FLAG", "router"]
