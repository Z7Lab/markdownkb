"""Pydantic request/response models for the buckets plugin."""

from pydantic import BaseModel, Field


class BucketSource(BaseModel):
    path: str = Field(..., min_length=1)
    glob: str = Field("**/*.md")


class CreateBucketRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sources: list[BucketSource] = Field(default_factory=list)
    expires_in: int | None = Field(None, ge=60, description="Seconds until expiry")
    color: str | None = Field(None, max_length=20, description="Hex color for this bucket")
    description: str | None = Field(None, max_length=1000, description="Optional description")


class BucketSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(5, ge=1, le=50)


class BucketChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class AddToBucketRequest(BaseModel):
    sources: list[BucketSource] = Field(..., min_length=1)


class BucketDocument(BaseModel):
    name: str = Field(..., min_length=1, max_length=500, description="Virtual filename (e.g. 'notes.md')")
    content: str = Field(..., min_length=1, max_length=500000, description="Raw markdown content")


class PushDocumentsRequest(BaseModel):
    documents: list[BucketDocument] = Field(..., min_length=1, max_length=2000)
    async_embed: bool = Field(False, description="Store immediately and embed in background")


class UpdateBucketRequest(BaseModel):
    expires_in: int | None = Field(None, description="Seconds from now, or null for permanent")
    name: str | None = Field(None, min_length=1, max_length=200, description="New bucket name")
    color: str | None = Field(None, max_length=20, description="Hex color")
    description: str | None = Field(None, max_length=1000, description="Optional description")
    scope_paths: list[str] | None = Field(None, description="Paths to include in retrieval scope (null = all files)")
    hidden: bool | None = Field(None, description="Hide from bucket lists and selectors without deleting")


class RenameDocumentRequest(BaseModel):
    old_path: str = Field(..., min_length=1)
    new_name: str = Field(..., min_length=1, max_length=500)


class BasepathRequest(BaseModel):
    base_path: str | None = Field(None)
