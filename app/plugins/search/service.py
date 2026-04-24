"""Search plugin service layer.

Extracted from ``router.py`` so the HTTP handler stays thin: the router's
job is request parsing and response shaping; this module holds the
plugin-specific config and result-shaping logic.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass

from app.config import Settings
from app.rag.retriever import Retriever
from app.services.query_service import build_enhanced_search_query, enhance_query

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "chunk_multiplier": 10,
    "exact_phrase_multiplier": 20,
    "exact_phrase_matching": True,
}


def get_search_config(settings: Settings) -> dict:
    """Return search plugin config with built-in defaults applied."""
    return {**_DEFAULTS, **settings.get_plugin_config("search")}


def group_results_by_file(results: list) -> list[dict]:
    """Group search results by source file, merging chunks into file-level results.

    For each file:
    - Use max score across all chunks as the file relevance
    - Collect all chunk texts as snippets
    - Track chunk count and score statistics

    Returns list of file-level results sorted by max score (descending).
    """
    file_groups: dict[str, list] = defaultdict(list)
    for r in results:
        path = r.metadata.get("source_path", "")
        if path:
            file_groups[path].append(r)

    grouped = []
    for path, chunks in file_groups.items():
        scores = [c.score for c in chunks]
        max_score = max(scores)
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)

        snippets = [
            {
                "text": c.document,
                "score": c.score,
                "heading": c.metadata.get("heading", ""),
            }
            for c in chunks
        ]
        snippets.sort(key=lambda s: s["score"], reverse=True)

        primary_chunk = max(chunks, key=lambda c: c.score)
        grouped.append({
            "document": primary_chunk.document,
            "snippets": snippets,
            "metadata": primary_chunk.metadata,
            "score": max_score,
            "chunk_count": len(chunks),
            "score_min": min_score,
            "score_max": max_score,
            "score_avg": avg_score,
        })

    grouped.sort(key=lambda x: x["score"], reverse=True)
    return grouped


@dataclass
class SearchOutcome:
    """Shaped result of ``perform_search`` — ready for the HTTP response."""

    grouped_results: list[dict]
    llm_offline: bool


def extract_exact_phrases(query: str, cfg: dict) -> tuple[str, list[str]]:
    """Pull "quoted phrases" out of the query when exact matching is on.

    Returns (clean_query_without_quotes, lowercased_phrases).
    """
    phrases: list[str] = []
    if cfg["exact_phrase_matching"]:
        phrases = [m.lower() for m in re.findall(r'"([^"]+)"', query)]
    clean = query.replace('"', '') if phrases else query
    return clean, phrases


def maybe_enhance_query(query: str, settings: Settings) -> tuple[str, bool]:
    """Optionally rewrite the query via LLM. Returns (query, llm_offline)."""
    if not settings.intelligent_search_enabled:
        return query, False
    enhanced = enhance_query(query, settings)
    if enhanced.error:
        logger.warning("Intelligent search failed, using original query: %s", enhanced.error)
        return query, True
    rewritten = build_enhanced_search_query(enhanced)
    logger.info("Enhanced query: %s -> %s", query, rewritten)
    return rewritten, False


def _search_buckets(bucket_retrievers, query: str, limit: int) -> list:
    results = []
    for br in bucket_retrievers:
        for r in br.search(query, top_k=limit):
            r.metadata["_bucket"] = "true"
            results.append(r)
    return results


def perform_search(
    *,
    query: str,
    top_k: int | None,
    retriever: Retriever,
    bucket_retrievers: list,
    bucket_only: bool,
    scope_folders: list[str] | None,
    allowed_paths: set[str] | None,
    exclude_patterns: list,
    settings: Settings,
) -> SearchOutcome:
    """Run the full search pipeline: enhance → retrieve → filter → group.

    Extracted so both the HTTP handler and future callers (MCP, tests)
    can run identical search orchestration.
    """
    cfg = get_search_config(settings)
    search_query, exact_phrases = extract_exact_phrases(query, cfg)
    effective_top_k = top_k if top_k is not None else settings.top_k

    search_query, llm_offline = maybe_enhance_query(search_query, settings)

    multiplier = cfg["exact_phrase_multiplier"] if exact_phrases else cfg["chunk_multiplier"]
    chunk_fetch_limit = effective_top_k * multiplier

    if bucket_only:
        chunk_results = _search_buckets(bucket_retrievers, search_query, chunk_fetch_limit)
    else:
        chunk_results = retriever.search(
            search_query,
            top_k=chunk_fetch_limit,
            folders_filter=scope_folders or None,
            allowed_paths=allowed_paths,
            exclude_patterns=exclude_patterns or None,
        )
        if bucket_retrievers:
            bucket_chunks = _search_buckets(bucket_retrievers, search_query, chunk_fetch_limit)
            chunk_results = sorted(chunk_results + bucket_chunks, key=lambda r: r.score, reverse=True)

    if exact_phrases:
        filtered = [r for r in chunk_results if all(p in r.document.lower() for p in exact_phrases)]
        logger.info("Exact phrase filter: %d -> %d chunks", len(chunk_results), len(filtered))
        chunk_results = filtered

    grouped = group_results_by_file(chunk_results)[:effective_top_k]
    return SearchOutcome(grouped_results=grouped, llm_offline=llm_offline)
