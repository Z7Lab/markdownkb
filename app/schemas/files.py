"""File-operation request models."""

from pydantic import BaseModel, Field


class FilePathRequest(BaseModel):
    """Request model for file path operations."""

    path: str = Field(..., min_length=1, max_length=4096)


class ToggleRagRequest(BaseModel):
    """Request model for toggling RAG inclusion."""

    path: str = Field(..., min_length=1, max_length=4096)
    include: bool


class FileActionRequest(BaseModel):
    """Request model for single-file index/unindex/reindex."""

    path: str = Field(..., min_length=1, max_length=4096)
    purge: bool = Field(False, description=(
        "When True, delete the tracking row entirely instead of resetting to pending. "
        "Use for explicit user-initiated removal — the file will not reappear in the "
        "Files tab or be re-indexed on next scan (assuming it matches a global_ignore "
        "pattern or has been deleted from disk). When False (default), the row is kept "
        "so re-indexing can resume from the same path."
    ))


class FileSearchRequest(BaseModel):
    """Request model for content-based file search (lightweight, no history)."""

    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(50, ge=1, le=200)


class SourceActionRequest(BaseModel):
    """Request model for bulk source operations (index/unindex all)."""

    source: str = Field(..., min_length=1, max_length=4096)
