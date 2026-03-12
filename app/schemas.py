"""Pydantic request/response models for the mdkb API."""

from pydantic import BaseModel, Field


# -- Search --

class SearchRequest(BaseModel):
    """Request model for search API endpoint."""

    query: str = Field(..., min_length=1, max_length=500)
    top_k: int | None = Field(None, ge=1, le=50)
    folder: str | None = None
    tag: str | None = None
    scope_id: str | None = None
    scope_ids: str | None = None  # Comma-separated scope IDs (multi-select)
    ad_hoc_tags: list[str] | None = None  # Ad-hoc tag filter (OR logic)
    parent_id: str | None = None  # Link re-queries into a version chain


class SummarizeRequest(BaseModel):
    """Request model for search summary (AI overview)."""

    query: str = Field(..., min_length=1, max_length=500)
    top_k: int | None = Field(None, ge=1, le=50)
    folder: str | None = None
    tag: str | None = None
    scope_id: str | None = None
    scope_ids: str | None = None
    ad_hoc_tags: list[str] | None = None
    search_id: str | None = None  # Optional: save summary when provided
    deep_research: bool = False  # Use MCTS deep research instead of single-pass
    deep_research_iterations: int | None = Field(None, ge=1, le=20)  # Override iteration count


# -- Chat --

class ChatRequest(BaseModel):
    """Request model for chat API endpoint."""

    message: str = Field(..., min_length=1, max_length=50000)
    conversation_history: list[dict] | None = None


class StreamChatRequest(BaseModel):
    """Request model for streaming chat API endpoint."""

    message: str = Field(..., min_length=1, max_length=50000)
    thread_id: str | None = None
    scope_id: str | None = None
    scope_ids: str | None = None
    ad_hoc_tags: list[str] | None = None


class SavePlanRequest(BaseModel):
    """Request model for saving conversation plan."""

    history: list[dict]


# -- Threads --

class RenameThreadRequest(BaseModel):
    """Request model for renaming conversation thread."""

    title: str = Field(..., min_length=1, max_length=500)


# -- Files / Sources --

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


class UpdateTagsRequest(BaseModel):
    """Request model for updating file tags."""

    path: str = Field(..., min_length=1, max_length=4096)
    tags: list[str]


class BulkUpdateTagsRequest(BaseModel):
    """Request model for bulk tag updates across multiple files."""

    paths: list[str] = Field(..., min_length=1)
    tags: list[str]
    mode: str = Field("add", pattern=r"^(add|remove|replace)$")


class FileSearchRequest(BaseModel):
    """Request model for content-based file search (lightweight, no history)."""

    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(50, ge=1, le=200)


class AutoTagPreviewRequest(BaseModel):
    """Request model for auto-tag dry run preview."""

    base_path: str = Field(..., description="Base directory to apply rules under")
    strategy: str = Field("subfolder", pattern=r"^(subfolder|doc_type)$")
    depth: int = Field(1, ge=1, le=5, description="Folder depth to extract tag from")
    tag_prefix: str = Field("", description="Optional prefix for generated tags")


class AutoTagApplyRequest(BaseModel):
    """Request model for applying auto-tag plan."""

    plan: dict = Field(..., description="Tag-to-paths mapping from preview")


class AddSourceRequest(BaseModel):
    """Request model for adding a source."""

    path: str = Field(..., min_length=1, max_length=4096)


class RemoveSourceRequest(BaseModel):
    """Request model for removing a source."""

    path: str = Field(..., min_length=1, max_length=4096)
    cleanup: bool = False  # Also unindex all files from this source


class SourceActionRequest(BaseModel):
    """Request model for bulk source operations (index/unindex all)."""

    source: str = Field(..., min_length=1, max_length=4096)


class AddProjectRootRequest(BaseModel):
    """Request model for adding a project root."""

    path: str = Field(..., min_length=1, max_length=4096)
    include: list[str] = Field(default_factory=lambda: ["*.md", "docs/**/*.md"])
    exclude: list[str] = Field(default_factory=list)


class UpdateProjectRootRequest(BaseModel):
    """Request model for updating a project root's patterns."""

    path: str = Field(..., min_length=1, max_length=4096)
    include: list[str] | None = None
    exclude: list[str] | None = None


class RemoveProjectRootRequest(BaseModel):
    """Request model for removing a project root."""

    path: str
    cleanup: bool = False


class IgnorePatternRequest(BaseModel):
    """Request model for adding/removing ignore patterns."""

    pattern: str


# -- Settings --

class ProviderSettingsRequest(BaseModel):
    """Request model for provider settings."""

    name: str
    model: str
    api_base: str = ""
    api_key: str = ""


class TestConnectionRequest(BaseModel):
    """Request model for testing LLM connection."""

    name: str
    model: str
    api_base: str = ""
    api_key: str = ""


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
    api_key: str = ""


class ModelInfoRequest(BaseModel):
    """Request model for getting model capabilities."""

    model: str
    api_base: str = ""


class LlmParamsRequest(BaseModel):
    """Request model for updating LLM generation parameters."""

    temperature: float = Field(..., ge=0.0, le=2.0)
    max_tokens: int = Field(..., ge=1, le=128000)
    num_ctx: int | None = Field(None, ge=1024, le=1048576)


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


# -- Planner --

class PlanRequest(BaseModel):
    """Request model for MCTS plan generation."""

    request: str = Field(..., min_length=1, max_length=50000)
    iterations: int = Field(3, ge=1, le=10)
    n_approaches: int = Field(3, ge=1, le=10)
    skill_names: list[str] | None = None
    scope_id: str | None = None
    scope_ids: str | None = None
    ad_hoc_tags: list[str] | None = None


# -- Logging --

class LogLevelRequest(BaseModel):
    """Request model for setting log level."""

    level: str = Field(..., pattern=r"^(INFO|DEBUG)$")


# -- Export --

class ExportRequest(BaseModel):
    """Request model for exporting conversation history."""

    format: str = "json"
