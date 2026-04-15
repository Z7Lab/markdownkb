"""Docmap plugin service layer.

Holds cache-key construction and scope/bucket orchestration that previously
lived inline in ``router.py``. The router imports these helpers instead of
defining them next to the HTTP handlers.
"""


def cache_key(
    source_roots: list[str] | None,
    scope_tags: list[str] | None,
    ad_hoc_tags: list[str] | None,
    top_k: int,
    word_clouds: bool = True,
    min_weight: float = 0.0,
    exclude_patterns: list[str] | None = None,
) -> tuple:
    """Build a stable, hashable cache key for a graph query."""
    roots = frozenset(source_roots) if source_roots else frozenset()
    tags = frozenset(scope_tags) if scope_tags else frozenset()
    adhoc = frozenset(ad_hoc_tags) if ad_hoc_tags else frozenset()
    excludes = frozenset(exclude_patterns) if exclude_patterns else frozenset()
    return (roots, tags, adhoc, top_k, word_clouds, min_weight, excludes)
