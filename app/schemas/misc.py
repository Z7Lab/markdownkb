"""Misc request models: logging, export."""

from pydantic import BaseModel, Field


class LogLevelRequest(BaseModel):
    """Request model for setting log level."""

    level: str = Field(..., pattern=r"^(INFO|DEBUG|OFF)$")


class ExportRequest(BaseModel):
    """Request model for exporting conversation history."""

    format: str = "json"
