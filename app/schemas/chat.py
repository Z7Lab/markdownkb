"""Chat, thread, and plan-save request models."""

from pydantic import BaseModel, Field, field_validator

from app.schemas._common import normalize_id_list


class ChatRequest(BaseModel):
    """Request model for chat API endpoint."""

    message: str = Field(..., min_length=1, max_length=50000)
    conversation_history: list[dict] | None = None


class StreamChatRequest(BaseModel):
    """Request model for streaming chat API endpoint."""

    message: str = Field(..., min_length=1, max_length=50000)
    thread_id: str | None = None
    scope_id: str | None = None
    scope_ids: list[str] | None = None
    ad_hoc_tags: list[str] | None = None
    bucket_ids: list[str] | None = None
    bucket_file_paths: list[str] | None = None

    _normalize_scope_ids = field_validator("scope_ids", mode="before")(normalize_id_list)
    _normalize_bucket_ids = field_validator("bucket_ids", mode="before")(normalize_id_list)


class SavePlanRequest(BaseModel):
    """Request model for saving conversation plan."""

    history: list[dict]


class RenameThreadRequest(BaseModel):
    """Request model for renaming conversation thread."""

    title: str = Field(..., min_length=1, max_length=500)
