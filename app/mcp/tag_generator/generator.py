"""AI-powered tag generation for markdown files with safety mechanisms."""

import logging
import shutil
from datetime import datetime
from pathlib import Path

import frontmatter
import yaml

logger = logging.getLogger(__name__)


class TagGenerationError(Exception):
    """Raised when tag generation fails."""
    pass


def backup_file(filepath: str) -> str:
    """Create a timestamped backup of the file before modification."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_suffix(f".{timestamp}.backup{path.suffix}")
    shutil.copy2(path, backup_path)
    logger.info(f"Created backup: {backup_path}")
    return str(backup_path)


def read_markdown_with_frontmatter(filepath: str) -> tuple[dict, str]:
    """
    Read a markdown file and separate frontmatter from content.

    Returns:
        (frontmatter_dict, content_string)
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(path, "r", encoding="utf-8") as f:
        post = frontmatter.load(f)

    return dict(post.metadata), post.content


def write_markdown_with_frontmatter(
    filepath: str,
    frontmatter_dict: dict,
    content: str,
    create_backup: bool = True
) -> str:
    """
    Write frontmatter and content back to a markdown file.

    Args:
        filepath: Path to the markdown file
        frontmatter_dict: Dictionary of frontmatter metadata
        content: The markdown content (without frontmatter)
        create_backup: Whether to create a backup before writing

    Returns:
        Path to backup file if created, else empty string
    """
    backup_path = ""
    if create_backup:
        backup_path = backup_file(filepath)

    # Use frontmatter library to ensure proper formatting
    post = frontmatter.Post(content, **frontmatter_dict)

    # Write to file
    path = Path(filepath)
    with open(path, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))

    logger.info(f"Updated frontmatter in {filepath}")
    return backup_path


def get_existing_tags(frontmatter_dict: dict) -> list[str]:
    """Extract existing tags from frontmatter metadata."""
    tags = frontmatter_dict.get("tags", [])
    if isinstance(tags, str):
        # Handle comma-separated string
        return [t.strip() for t in tags.split(",") if t.strip()]
    elif isinstance(tags, list):
        return [str(t).strip() for t in tags if t]
    return []


def format_tags_for_frontmatter(tags: list[str]) -> list[str]:
    """
    Format tags as a list for YAML frontmatter.

    Returns a deduplicated, sorted list of lowercase tags.
    """
    # Normalize: lowercase, dedupe, sort
    normalized = sorted(set(t.lower().strip() for t in tags if t.strip()))
    return normalized


def preview_frontmatter_changes(
    original_frontmatter: dict,
    new_tags: list[str]
) -> str:
    """
    Generate a preview showing frontmatter changes.

    Returns a string showing the diff.
    """
    old_tags = get_existing_tags(original_frontmatter)
    formatted_tags = format_tags_for_frontmatter(new_tags)

    lines = ["=" * 60]
    lines.append("FRONTMATTER PREVIEW")
    lines.append("=" * 60)

    # Show existing tags
    if old_tags:
        lines.append("\nCurrent tags:")
        for tag in old_tags:
            lines.append(f"  - {tag}")
    else:
        lines.append("\nNo existing tags")

    # Show new tags
    lines.append("\nProposed tags:")
    for tag in formatted_tags:
        if tag in old_tags:
            lines.append(f"  - {tag} (existing)")
        else:
            lines.append(f"  - {tag} (NEW)")

    # Show removed tags
    removed = set(old_tags) - set(formatted_tags)
    if removed:
        lines.append("\nWill be removed:")
        for tag in removed:
            lines.append(f"  - {tag}")

    lines.append("\n" + "=" * 60)

    # Show other frontmatter that will be preserved
    other_fields = {k: v for k, v in original_frontmatter.items() if k != "tags"}
    if other_fields:
        lines.append("\nOther frontmatter (will be preserved):")
        for key, value in other_fields.items():
            lines.append(f"  {key}: {value}")

    lines.append("=" * 60)
    return "\n".join(lines)


def apply_tags_to_file(
    filepath: str,
    tags: list[str],
    merge_with_existing: bool = True,
    create_backup: bool = True
) -> dict:
    """
    Apply tags to a markdown file's frontmatter.

    Args:
        filepath: Path to the markdown file
        tags: List of tags to apply
        merge_with_existing: If True, merge with existing tags. If False, replace.
        create_backup: Whether to create a backup before modifying

    Returns:
        Dictionary with status and info:
        {
            "status": "success" | "error",
            "backup_path": str,
            "old_tags": list[str],
            "new_tags": list[str],
            "message": str
        }
    """
    try:
        # Read current file
        frontmatter_dict, content = read_markdown_with_frontmatter(filepath)
        old_tags = get_existing_tags(frontmatter_dict)

        # Determine final tags
        if merge_with_existing:
            # Merge: combine old and new, then normalize
            combined = old_tags + tags
            final_tags = format_tags_for_frontmatter(combined)
        else:
            # Replace: use only new tags
            final_tags = format_tags_for_frontmatter(tags)

        # Update frontmatter
        frontmatter_dict["tags"] = final_tags

        # Write back
        backup_path = write_markdown_with_frontmatter(
            filepath,
            frontmatter_dict,
            content,
            create_backup=create_backup
        )

        return {
            "status": "success",
            "backup_path": backup_path,
            "old_tags": old_tags,
            "new_tags": final_tags,
            "message": f"Successfully updated tags in {filepath}"
        }

    except (FileNotFoundError, OSError, yaml.YAMLError) as e:
        logger.error("Failed to apply tags to %s: %s", filepath, e)
        return {
            "status": "error",
            "backup_path": "",
            "old_tags": [],
            "new_tags": [],
            "message": f"Error: {str(e)}"
        }


def restore_from_backup(backup_path: str, original_path: str) -> None:
    """Restore a file from its backup."""
    if not Path(backup_path).exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    shutil.copy2(backup_path, original_path)
    logger.info(f"Restored {original_path} from backup")


# Example usage functions for LLM integration

def generate_tags_from_content(
    content: str,
    existing_tags_in_kb: list[str],
    max_tags: int = 5
) -> list[str]:
    """
    Use LLM to generate tags for markdown content.

    This would be called by the chat service with RAG context.

    Args:
        content: The markdown content to analyze
        existing_tags_in_kb: List of tags already in the knowledge base (for consistency)
        max_tags: Maximum number of tags to generate

    Returns:
        List of suggested tags
    """
    # This is a placeholder - the actual implementation would use the LLM
    # See below for integration with chat service
    raise NotImplementedError("Integrate with chat service LLM")


def get_similar_document_tags(
    filepath: str,
    retriever,
    top_k: int = 5
) -> list[str]:
    """
    Get tags from similar documents in the knowledge base.

    Args:
        filepath: Path to the file to analyze
        retriever: The RAG retriever instance
        top_k: Number of similar documents to consider

    Returns:
        List of unique tags from similar documents
    """
    # Read the file content
    _, content = read_markdown_with_frontmatter(filepath)

    # Use retriever to find similar documents
    # This gives context about what tags exist in similar docs
    results = retriever.search(content[:500], top_k=top_k)  # Use first 500 chars as query

    # Extract tags from similar documents
    tags = set()
    for result in results:
        doc_tags = result.metadata.get("tags", "")
        if doc_tags:
            for tag in doc_tags.split(", "):
                if tag.strip():
                    tags.add(tag.strip())

    return sorted(tags)
