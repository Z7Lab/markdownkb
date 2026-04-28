"""Source-directory and project-root request models."""

from pydantic import BaseModel, Field


class AddSourceRequest(BaseModel):
    """Request model for adding a source."""

    path: str = Field(..., min_length=1, max_length=4096)


class RemoveSourceRequest(BaseModel):
    """Request model for removing a source."""

    path: str = Field(..., min_length=1, max_length=4096)
    cleanup: bool = False


class UpdateSourceRequest(BaseModel):
    """Request model for updating source flags (writable, versioned, tier)."""

    path: str = Field(..., min_length=1, max_length=4096)
    writable: bool | None = None
    versioned: bool | None = None
    tier: int | None = Field(None, ge=-1, le=1)


class AddProjectRootRequest(BaseModel):
    """Request model for adding a project root."""

    path: str = Field(..., min_length=1, max_length=4096)
    include: list[str] = Field(default_factory=lambda: ["*.md", "docs/**/*.md"])
    exclude: list[str] = Field(default_factory=list)
    title: str | None = Field(None, max_length=128)


class UpdateProjectRootRequest(BaseModel):
    """Request model for updating a project root's patterns."""

    path: str = Field(..., min_length=1, max_length=4096)
    include: list[str] | None = None
    exclude: list[str] | None = None
    title: str | None = None


class RemoveProjectRootRequest(BaseModel):
    """Request model for removing a project root."""

    path: str
    cleanup: bool = False


class IgnorePatternRequest(BaseModel):
    """Request model for adding/removing ignore patterns."""

    pattern: str
