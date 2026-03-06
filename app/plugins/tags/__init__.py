"""Tag generation plugin — AI-powered frontmatter tagging for markdown files."""

from app.plugins.tags.router import router

FEATURE_FLAG = "mcp_tag_generator"

__all__ = ["FEATURE_FLAG", "router"]
