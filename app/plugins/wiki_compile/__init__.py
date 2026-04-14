"""Wiki Compile plugin — Karpathy-style LLM-driven wiki ingestion."""

from app.plugins.wiki_compile.router import router

FEATURE_FLAG = "wiki_compile"

__all__ = ["FEATURE_FLAG", "router"]
