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
    bucket_id: str | None = None  # Search within a specific bucket


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
    bucket_id: str | None = None  # Summarize within a specific bucket
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
    bucket_id: str | None = None  # Chat within a specific bucket


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


class FileSearchRequest(BaseModel):
    """Request model for content-based file search (lightweight, no history)."""

    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(50, ge=1, le=200)


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
    """Request model for provider settings.

    API keys must be provided via Docker secrets or environment variables,
    not in request bodies.
    """

    name: str
    model: str
    api_base: str = ""


class TestConnectionRequest(BaseModel):
    """Request model for testing LLM connection.

    Only ``name`` is required — ``model`` and ``api_base`` are filled
    from the provider config when omitted.
    """

    name: str
    model: str = ""
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


class OllamaPullRequest(BaseModel):
    """Request model for pulling an Ollama model."""

    model_name: str = Field(..., min_length=1, max_length=200)
    api_base: str = ""


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
    bucket_id: str | None = None  # Plan within a specific bucket


# -- Logging --

class LogLevelRequest(BaseModel):
    """Request model for setting log level."""

    level: str = Field(..., pattern=r"^(INFO|DEBUG)$")


# -- Export --

class ExportRequest(BaseModel):
    """Request model for exporting conversation history."""

    format: str = "json"


# -- Plugin Settings --

class PluginConfigRequest(BaseModel):
    """Request model for updating plugin configuration."""

    config: dict[str, str | int | float | bool | None]


# -- Presets --

class CreatePresetRequest(BaseModel):
    """Request model for creating a retrieval preset."""

    name: str = Field(..., min_length=1, max_length=200)
    settings: dict | None = None


class UpdatePresetRequest(BaseModel):
    """Request model for updating a retrieval preset."""

    name: str | None = Field(None, min_length=1, max_length=200)
    settings: dict | None = None


# -- Search --

class RenameSearchRequest(BaseModel):
    """Request model for renaming a search."""

    query: str = Field(..., min_length=1, max_length=500)
