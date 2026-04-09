"""Tag Generator MCP Tool - AI-powered tag generation for markdown files."""

from .generator import (
    apply_tags_to_file,
    backup_file,
    format_tags_for_frontmatter,
    get_existing_tags,
    get_similar_document_tags,
    preview_frontmatter_changes,
    read_markdown_with_frontmatter,
    write_markdown_with_frontmatter,
)
from .llm import (
    auto_tag_file_interactive,
    bulk_tag_directory,
    generate_tags_with_llm,
)

__all__ = [
    # Generator functions
    "read_markdown_with_frontmatter",
    "write_markdown_with_frontmatter",
    "get_existing_tags",
    "format_tags_for_frontmatter",
    "preview_frontmatter_changes",
    "apply_tags_to_file",
    "backup_file",
    "get_similar_document_tags",
    # LLM functions
    "generate_tags_with_llm",
    "auto_tag_file_interactive",
    "bulk_tag_directory",
]
