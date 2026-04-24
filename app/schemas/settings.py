"""Settings, LLM, preset, and plugin configuration request models."""

from pydantic import BaseModel, Field


class ProviderSettingsRequest(BaseModel):
    """Request model for provider settings."""

    name: str
    model: str
    api_base: str = ""
    api_key: str = ""


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


class PluginConfigRequest(BaseModel):
    """Request model for updating plugin configuration."""

    config: dict[str, str | int | float | bool | None]


class CreatePresetRequest(BaseModel):
    """Request model for creating a retrieval preset."""

    name: str = Field(..., min_length=1, max_length=200)
    settings: dict[str, str | int | float | bool | None] | None = None


class UpdatePresetRequest(BaseModel):
    """Request model for updating a retrieval preset."""

    name: str | None = Field(None, min_length=1, max_length=200)
    settings: dict[str, str | int | float | bool | None] | None = None
