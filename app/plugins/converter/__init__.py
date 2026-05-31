"""Converter plugin — batch convert documents to markdown for indexing."""

from fastapi import APIRouter

from app.plugins.converter.router import import_router
from app.plugins.converter.router import router as converter_router

# Aggregate the converter endpoints (/api/v1/converter/*) and the import
# capabilities endpoint (/api/v1/import/*) under one router so both are mounted
# when the converter plugin is enabled.
router = APIRouter()
router.include_router(converter_router)
router.include_router(import_router)

FEATURE_FLAG = "converter"

__all__ = ["FEATURE_FLAG", "router"]
