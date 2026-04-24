"""Embedding model and indexing request models."""

from pydantic import BaseModel, Field


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
