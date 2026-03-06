"""Write API plugin — HTTP endpoint for creating/updating markdown documents."""

from app.plugins.write_api.router import router

FEATURE_FLAG = "write_api"

__all__ = ["FEATURE_FLAG", "router"]
