"""MCP tool: search and return full document content.

Unlike ``search`` which returns chunks, this returns complete document
content for the top matching files — ideal for embedding into prompts.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from app.config import Settings
from app.mcp.history import record_search
from app.mcp.scope import resolve_mcp_scope
from app.rag.retriever import Retriever
from app.storage.trackingdb import TrackingDB

TOOL = {
    "name": "search_documents",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler(query: str, top_k: int | None = None, max_chars: int = 15000,
            tags: list[str] | None = None,
            scope_id: str | None = None) -> dict:
    """Search and return full documents matching a query.

    Unlike ``search`` which returns individual chunks, this returns the
    full content of the top matching files — deduplicated by source path.
    Use this when you need complete documents for context rather than
    individual chunks. Each result includes a ``path`` that can also be
    passed to ``get_file(path)`` for paginated reading of large files.

    Args:
        query: Search query string.
        top_k: Maximum number of documents to return. Defaults to the
               ``top_k`` value configured in settings (typically 5).
        max_chars: Character budget for total returned content (default
                   15000).  Documents are included in score order until
                   the budget is exhausted.
        tags: Optional list of tags to filter by (OR logic — documents
              matching any tag are included).  Use the list_tags tool
              to discover available tags.
        scope_id: Optional scope ID to restrict search to specific folders
                  and/or tags.  Use the list_scopes tool to discover
                  available scopes.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    retriever: Retriever = deps["retriever"]
    tracking: TrackingDB = deps["tracking"]
    settings: Settings = deps["settings"]
    if top_k is None:
        top_k = settings.top_k

    # Resolve scope + ad-hoc tags into folder filter and allowed paths
    folders_filter, allowed_paths, exclude_patterns = resolve_mcp_scope(
        ctx, scope_id, ad_hoc_tags=tags,
    )

    # If tags/scope resolved to zero matching paths, short-circuit
    if (tags or scope_id) and allowed_paths is not None and not allowed_paths:
        response: dict = {"documents": [], "total_chars": 0}
        if tags:
            response["tags_filter"] = tags
        if scope_id:
            response["scope_id"] = scope_id
        return response

    # 1. Search chunks (fetch more than top_k to improve dedup coverage)
    results = retriever.search(
        query, top_k=top_k * 5,
        folders_filter=folders_filter, allowed_paths=allowed_paths, exclude_patterns=exclude_patterns,
    )

    # 2. Deduplicate by source path, keeping the highest score per file
    best_by_file: dict[str, float] = {}
    for r in results:
        src = r.metadata.get("source_path", "")
        if not src:
            continue
        if src not in best_by_file or r.score > best_by_file[src]:
            best_by_file[src] = r.score

    # 3. Rank files by best chunk score
    ranked = sorted(best_by_file.items(), key=lambda x: x[1], reverse=True)

    # 4. Read full file content for top_k files within max_chars budget
    documents = []
    total_chars = 0
    for source_path, score in ranked[:top_k]:
        record = tracking.get_file(source_path)
        if not record:
            continue

        try:
            content = Path(source_path).read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Cannot read document %s: %s", source_path, e)
            documents.append({
                "path": source_path,
                "title": Path(source_path).stem.replace("-", " ").replace("_", " "),
                "content": "",
                "score": round(score, 4),
                "error": f"Could not read file: {e}",
            })
            continue

        # Truncate individual document if it would blow the budget
        remaining = max_chars - total_chars
        if remaining <= 0:
            break
        if len(content) > remaining:
            content = content[:remaining] + "\n\n[... truncated ...]"

        total_chars += len(content)
        documents.append({
            "path": source_path,
            "title": Path(source_path).stem.replace("-", " ").replace("_", " "),
            "content": content,
            "score": round(score, 4),
        })

    # Build rich history data matching the web UI search format
    result_details = [
        {"path": d["path"], "score": d["score"]}
        for d in documents
    ]
    result_data = [
        {
            "document": d["content"][:500],  # Store preview, not full content
            "snippets": [{"text": d["content"][:500], "score": d["score"], "heading": d["title"]}],
            "metadata": {"source_path": d["path"]},
            "score": d["score"],
            "chunk_count": 1,
            "score_min": d["score"],
            "score_max": d["score"],
            "score_avg": d["score"],
        }
        for d in documents
    ]

    record_search(
        ctx, query, documents, tool_name="search_documents",
        result_details=result_details, result_data=result_data,
    )

    response: dict = {
        "documents": documents,
        "total_chars": total_chars,
    }
    if tags:
        response["tags_filter"] = tags
    if scope_id:
        response["scope_id"] = scope_id
    return response
