"""Tag generation API endpoints (optional MCP feature)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_retriever, get_settings
from app.mcp.tag_generator import (
    apply_tags_to_file,
    auto_tag_file_interactive,
    bulk_tag_directory,
)
from app.rag.retriever import Retriever
from app.ratelimit import LLM, STANDARD, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tags", tags=["tags"])


class GenerateTagsRequest(BaseModel):
    """Request to generate tags for a file."""
    file_path: str = Field(..., description="Path to markdown file")
    use_similar_docs: bool = Field(
        default=True,
        description="Use tags from similar documents as context"
    )
    auto_apply: bool = Field(
        default=False,
        description="Automatically apply tags (with backup)"
    )


class ApplyTagsRequest(BaseModel):
    """Request to apply tags to a file."""
    file_path: str = Field(..., description="Path to markdown file")
    tags: list[str] = Field(..., description="Tags to apply")
    merge_with_existing: bool = Field(
        default=True,
        description="Merge with existing tags or replace"
    )
    create_backup: bool = Field(
        default=True,
        description="Create backup before modifying file"
    )


class BulkTagRequest(BaseModel):
    """Request to tag multiple files in a directory."""
    directory: str = Field(..., description="Directory to scan")
    pattern: str = Field(default="*.md", description="Glob pattern for files")
    auto_apply: bool = Field(
        default=False,
        description="Automatically apply tags to all files"
    )
    max_files: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum files to process"
    )


def check_feature_enabled(settings: Settings = Depends(get_settings)):
    """Dependency to check if tag generation feature is enabled."""
    if not settings.features.get("mcp_tag_generator", False):
        raise HTTPException(
            status_code=403,
            detail="Tag generation feature is disabled. Enable 'mcp_tag_generator' in settings.yaml"
        )


@router.post("/generate")
@limiter.limit(LLM)
def generate_tags(
    request: Request,
    req: GenerateTagsRequest,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    _: None = Depends(check_feature_enabled),
):
    """
    Generate AI-powered tags for a markdown file.

    This endpoint uses LLM to analyze the file content and suggest relevant tags.
    It can optionally use similar documents in the knowledge base for context.

    Returns a preview of changes without modifying the file (unless auto_apply=True).
    """
    try:
        result = auto_tag_file_interactive(
            req.file_path,
            retriever,
            settings,
            auto_apply=req.auto_apply
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return result

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Tag generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Tag generation failed: {str(e)}")


@router.post("/apply")
@limiter.limit(STANDARD)
def apply_tags(
    request: Request,
    req: ApplyTagsRequest,
    _settings: Settings = Depends(get_settings),
    __: None = Depends(check_feature_enabled),
):
    """
    Apply specific tags to a markdown file's frontmatter.

    Creates a backup before modifying the file.
    Can merge with existing tags or replace them entirely.
    """
    try:
        result = apply_tags_to_file(
            req.file_path,
            req.tags,
            merge_with_existing=req.merge_with_existing,
            create_backup=req.create_backup
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return result

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Tag application error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to apply tags: {str(e)}")


@router.post("/bulk")
@limiter.limit(LLM)
def bulk_tag(
    request: Request,
    req: BulkTagRequest,
    retriever: Retriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
    _: None = Depends(check_feature_enabled),
):
    """
    Generate tags for multiple files in a directory.

    Processes up to max_files markdown files matching the pattern.
    Returns results for each file processed.

    Warning: With auto_apply=True, this modifies files in bulk!
    """
    try:
        results = bulk_tag_directory(
            req.directory,
            retriever,
            settings,
            pattern=req.pattern,
            auto_apply=req.auto_apply,
            max_files=req.max_files
        )

        return {
            "processed": len(results),
            "results": results
        }

    except Exception as e:
        logger.error(f"Bulk tagging error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Bulk tagging failed: {str(e)}")
