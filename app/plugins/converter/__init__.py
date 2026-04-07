"""Converter plugin — batch convert documents to markdown for indexing."""

from app.plugins.converter.router import router

FEATURE_FLAG = "converter"

__all__ = ["FEATURE_FLAG", "router"]
