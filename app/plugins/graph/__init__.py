"""Knowledge graph plugin — document similarity visualization."""

from app.plugins.graph.router import router

FEATURE_FLAG = "graph"

__all__ = ["FEATURE_FLAG", "router"]
