"""Search plugin service layer.

Extracted from ``router.py`` so the HTTP handler stays thin: the router's
job is request parsing and response shaping; this module holds the
plugin-specific config and result-shaping logic.
"""

from collections import defaultdict

from app.config import Settings

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
