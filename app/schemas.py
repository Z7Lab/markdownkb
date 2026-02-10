"""Pydantic request/response models for the mdkb API."""

from pydantic import BaseModel, Field


# -- Search --

class SearchRequest(BaseModel):
    """Request model for search API endpoint."""

    query: str = Field(..., min_length=1, max_length=10000)
    top_k: int | None = Field(None, ge=1, le=50)
    folder: str | None = None
    tag: str | None = None
    parent_id: str | None = None  # Link re-queries into a version chain


class SummarizeRequest(BaseModel):
    """Request model for search summary (AI overview)."""

    query: str = Field(..., min_length=1, max_length=10000)
    top_k: int | None = Field(None, ge=1, le=50)
    folder: str | None = None
    tag: str | None = None
    search_id: str | None = None  # Optional: save summary when provided


# -- Chat --

class ChatRequest(BaseModel):
    """Request model for chat API endpoint."""

    message: str = Field(..., min_length=1, max_length=50000)
    conversation_history: list[dict] | None = None


class StreamChatRequest(BaseModel):
    """Request model for streaming chat API endpoint."""

    message: str = Field(..., min_length=1, max_length=50000)
    thread_id: str | None = None


class SavePlanRequest(BaseModel):
    """Request model for saving conversation plan."""

    history: list[dict]


# -- Threads --

class RenameThreadRequest(BaseModel):
    """Request model for renaming conversation thread."""

    title: str


# -- Files / Sources --

class FilePathRequest(BaseModel):
    """Request model for file path operations."""

    path: str


class ToggleRagRequest(BaseModel):
    """Request model for toggling RAG inclusion."""

    path: str
    include: bool


class FileActionRequest(BaseModel):
    """Request model for single-file index/unindex/reindex."""

    path: str


class AddSourceRequest(BaseModel):
    """Request model for adding a source."""

    path: str


class RemoveSourceRequest(BaseModel):
    """Request model for removing a source."""

    path: str


class IgnorePatternRequest(BaseModel):
    """Request model for adding/removing ignore patterns."""

    pattern: str


# -- Settings --

class ProviderSettingsRequest(BaseModel):
    """Request model for provider settings."""

    name: str
    model: str
    api_base: str = ""


class TestConnectionRequest(BaseModel):
    """Request model for testing LLM connection."""

    name: str
    model: str
    api_base: str = ""


class RefreshModelsRequest(BaseModel):
    """Request model for refreshing available models."""

    name: str
    api_base: str


class FeatureToggleRequest(BaseModel):
    """Request model for toggling feature flags."""

    name: str
    enabled: bool


class TestPromptRequest(BaseModel):
    """Request model for testing prompt with LLM."""

    prompt: str = Field(..., min_length=1, max_length=50000)
    provider: str = ""
    model: str = ""
    api_base: str = ""


class ModelInfoRequest(BaseModel):
    """Request model for getting model capabilities."""

    model: str
    api_base: str = ""


class SystemPromptRequest(BaseModel):
    """Request model for updating system prompt."""

    prompt: str


class SearchSummaryPromptRequest(BaseModel):
    """Request model for updating search summary prompt."""

    prompt: str


class RetrievalSettingsRequest(BaseModel):
    """Request model for updating retrieval/search settings."""

    top_k: int = Field(..., ge=1, le=50)
    score_threshold: float = Field(..., ge=0.0, le=1.0)
    hybrid_search: bool
    bm25_weight: float = Field(..., ge=0.0, le=1.0)


# -- Embeddings --

class EmbeddingModelRequest(BaseModel):
    """Request model for embedding model operations."""

    model_id: str


class IndexRequest(BaseModel):
    """Request model for triggering indexing."""

    force: bool = False


# -- MCP --

class McpToolConfigRequest(BaseModel):
    """Request model for updating MCP tool configuration."""

    tool_name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    config: dict


# -- Export --

class ExportRequest(BaseModel):
    """Request model for exporting conversation history."""

    format: str = "json"
