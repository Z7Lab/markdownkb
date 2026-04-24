"""Pydantic request/response models for the search plugin."""

from pydantic import BaseModel, Field, field_validator

from app.schemas._common import normalize_id_list


class SearchRequest(BaseModel):
    """Request model for search API endpoint."""

    query: str = Field(..., min_length=1, max_length=500)
    top_k: int | None = Field(None, ge=1, le=50)
    scope_id: str | None = None
    scope_ids: list[str] | None = None
    ad_hoc_tags: list[str] | None = None
    parent_id: str | None = None
    bucket_ids: list[str] | None = None

    _normalize_scope_ids = field_validator("scope_ids", mode="before")(normalize_id_list)
    _normalize_bucket_ids = field_validator("bucket_ids", mode="before")(normalize_id_list)


class SummarizeRequest(BaseModel):
    """Request model for search summary (AI overview)."""

    query: str = Field(..., min_length=1, max_length=500)
    top_k: int | None = Field(None, ge=1, le=50)
    scope_id: str | None = None
    scope_ids: list[str] | None = None
    ad_hoc_tags: list[str] | None = None
    search_id: str | None = None
    bucket_ids: list[str] | None = None
    deep_research: bool = False
    deep_research_iterations: int | None = Field(None, ge=1, le=20)

    _normalize_scope_ids = field_validator("scope_ids", mode="before")(normalize_id_list)
    _normalize_bucket_ids = field_validator("bucket_ids", mode="before")(normalize_id_list)


class RenameSearchRequest(BaseModel):
    """Request model for renaming a search."""

    query: str = Field(..., min_length=1, max_length=500)
