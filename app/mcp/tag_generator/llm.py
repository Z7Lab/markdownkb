"""LLM-powered tag generation using the retriever for context."""

import logging
from pathlib import Path

from app.config import Settings
from app.rag.llm import get_completion
from app.rag.retriever import Retriever

from .generator import (
    apply_tags_to_file,
    get_existing_tags,
    get_similar_document_tags,
    preview_frontmatter_changes,
    read_markdown_with_frontmatter,
)

logger = logging.getLogger(__name__)

TAG_GENERATION_PROMPT = """You are a helpful assistant that generates relevant tags for markdown documents.

Your task: Analyze the document content and suggest appropriate tags.

Guidelines:
- Generate 3-7 concise, relevant tags
- Use lowercase, hyphenated format (e.g., "web-development", "python", "tutorial")
- Consider the document's topic, concepts, technologies, and purpose
- If similar documents use certain tags, prefer consistency
- Avoid overly generic tags like "misc" or "other"
- Focus on searchability and categorization

Document Title: {title}

Document Content (excerpt):
{content}

Existing tags in knowledge base (for consistency):
{existing_kb_tags}

Tags from similar documents:
{similar_tags}

Respond with ONLY a comma-separated list of tags, nothing else.
Example: python, web-development, tutorial, fastapi, backend
"""


def generate_tags_with_llm(
    filepath: str,
    retriever: Retriever,
    settings: Settings,
    use_similar_docs: bool = True,
    content_preview_length: int = 1000,
) -> dict:
    """
    Generate tags for a markdown file using LLM with RAG context.

    Args:
        filepath: Path to the markdown file
        retriever: RAG retriever for finding similar docs and existing tags
        settings: App settings for LLM config
        use_similar_docs: Whether to use similar document tags for context
        content_preview_length: How many chars of content to send to LLM

    Returns:
        Dictionary with:
        {
            "status": "success" | "error",
            "suggested_tags": list[str],
            "existing_tags": list[str],
            "similar_tags": list[str],
            "preview": str,  # Preview of changes
            "message": str
        }
    """
    try:
        # Read file
        frontmatter_dict, content = read_markdown_with_frontmatter(filepath)
        existing_tags = get_existing_tags(frontmatter_dict)

        # Get title from frontmatter or filename
        title = frontmatter_dict.get("title", Path(filepath).stem)

        # Get all unique tags in knowledge base
        all_kb_tags = retriever.get_unique_tags()

        # Get tags from similar documents (if enabled)
        similar_tags = []
        if use_similar_docs:
            similar_tags = get_similar_document_tags(filepath, retriever, top_k=5)

        # Prepare LLM prompt
        content_preview = content[:content_preview_length]
        prompt = TAG_GENERATION_PROMPT.format(
            title=title,
            content=content_preview,
            existing_kb_tags=", ".join(all_kb_tags[:20]) if all_kb_tags else "none",
            similar_tags=", ".join(similar_tags) if similar_tags else "none"
        )

        # Call LLM
        messages = [{"role": "user", "content": prompt}]
        response = get_completion(messages, settings)

        # Parse response
        suggested_tags_str = response.strip()
        suggested_tags = [
            tag.strip().lower()
            for tag in suggested_tags_str.split(",")
            if tag.strip()
        ]

        # Generate preview
        preview = preview_frontmatter_changes(frontmatter_dict, suggested_tags)

        return {
            "status": "success",
            "suggested_tags": suggested_tags,
            "existing_tags": existing_tags,
            "similar_tags": similar_tags,
            "preview": preview,
            "message": f"Generated {len(suggested_tags)} tags for {filepath}"
        }

    except Exception as e:
        logger.error(f"Tag generation failed: {e}", exc_info=True)
        return {
            "status": "error",
            "suggested_tags": [],
            "existing_tags": [],
            "similar_tags": [],
            "preview": "",
            "message": f"Error: {str(e)}"
        }


def auto_tag_file_interactive(
    filepath: str,
    retriever: Retriever,
    settings: Settings,
    auto_apply: bool = False,
) -> dict:
    """
    Generate tags and optionally apply them to a file.

    This is the high-level function that would be called by a skill or API.

    Args:
        filepath: Path to markdown file
        retriever: RAG retriever
        settings: App settings
        auto_apply: If True, apply tags immediately. If False, return preview only.

    Returns:
        Dictionary with results and status
    """
    # Generate tags
    result = generate_tags_with_llm(filepath, retriever, settings)

    if result["status"] == "error":
        return result

    # If auto_apply, update the file
    if auto_apply:
        from app.mcp.tag_generator import apply_tags_to_file

        apply_result = apply_tags_to_file(
            filepath,
            result["suggested_tags"],
            merge_with_existing=True,
            create_backup=True
        )

        result["applied"] = True
        result["backup_path"] = apply_result.get("backup_path", "")
        result["final_tags"] = apply_result.get("new_tags", [])
    else:
        result["applied"] = False
        result["backup_path"] = ""
        result["final_tags"] = []

    return result


def bulk_tag_directory(
    directory: str,
    retriever: Retriever,
    settings: Settings,
    pattern: str = "*.md",
    auto_apply: bool = False,
    max_files: int = 50,
) -> list[dict]:
    """
    Generate tags for multiple files in a directory.

    Args:
        directory: Directory to scan
        retriever: RAG retriever
        settings: App settings
        pattern: Glob pattern for files to process
        auto_apply: Whether to apply tags automatically
        max_files: Maximum number of files to process

    Returns:
        List of results for each file
    """
    from pathlib import Path

    dir_path = Path(directory)
    if not dir_path.exists():
        return [{"status": "error", "message": f"Directory not found: {directory}"}]

    results = []
    count = 0

    for filepath in dir_path.rglob(pattern):
        if count >= max_files:
            break

        if filepath.is_file():
            logger.info(f"Processing {filepath}")
            result = auto_tag_file_interactive(
                str(filepath),
                retriever,
                settings,
                auto_apply=auto_apply
            )
            result["file"] = str(filepath)
            results.append(result)
            count += 1

    return results
