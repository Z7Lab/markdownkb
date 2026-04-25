"""Misc request models: logging, export."""

from pydantic import BaseModel, Field


class LogLevelRequest(BaseModel):
    """Request model for setting log level."""

    level: str = Field(..., pattern=r"^(INFO|DEBUG|OFF)$")


class LoggerOverridesRequest(BaseModel):
    """Request model for updating per-logger level overrides."""

    overrides: dict[str, str] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    """Request model for exporting conversation history."""

    format: str = "json"
