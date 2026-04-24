"""MCP tool configuration request models."""

from pydantic import BaseModel, Field


class McpToolConfigRequest(BaseModel):
    """Request model for updating MCP tool configuration."""

    tool_name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    config: dict
