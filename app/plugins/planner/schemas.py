"""Pydantic request/response models for the planner plugin."""

from pydantic import BaseModel, Field, field_validator

from app.schemas._common import normalize_id_list


class PlanRequest(BaseModel):
    """Request model for MCTS plan generation."""

    request: str = Field(..., min_length=1, max_length=50000)
    iterations: int = Field(3, ge=1, le=10)
    n_approaches: int = Field(3, ge=1, le=10)
    skill_names: list[str] | None = None
    scope_id: str | None = None
    scope_ids: list[str] | None = None
    ad_hoc_tags: list[str] | None = None
    bucket_ids: list[str] | None = None

    _normalize_scope_ids = field_validator("scope_ids", mode="before")(normalize_id_list)
    _normalize_bucket_ids = field_validator("bucket_ids", mode="before")(normalize_id_list)
