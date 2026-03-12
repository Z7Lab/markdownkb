"""Retrieval and search configuration mixin."""


class RetrievalMixin:
    """Mixin providing retrieval settings: top_k, thresholds, hybrid search, BM25."""

    @property
    def top_k(self) -> int:
        """Return the number of results per search."""
        return self._data.get("retrieval", {}).get("top_k", 5)

    @property
    def score_threshold(self) -> float:
        """Return the minimum similarity score threshold."""
        return self._data.get("retrieval", {}).get(
            "score_threshold", 0.3
        )

    @property
    def hybrid_search(self) -> bool:
        """Return whether hybrid BM25+vector search is enabled."""
        return self._data.get("retrieval", {}).get(
            "hybrid_search", True
        )

    @property
    def bm25_weight(self) -> float:
        """Return the BM25 weight in hybrid search."""
        return self._data.get("retrieval", {}).get("bm25_weight", 0.5)

    @property
    def default_top_k(self) -> int:
        """Return the built-in default top_k value."""
        return 5

    @property
    def default_score_threshold(self) -> float:
        """Return the built-in default score_threshold value."""
        return 0.3

    @property
    def default_hybrid_search(self) -> bool:
        """Return the built-in default hybrid_search value."""
        return True

    @property
    def default_bm25_weight(self) -> float:
        """Return the built-in default bm25_weight value."""
        return 0.5

    @top_k.setter
    def top_k(self, value: int):
        """Set the number of results per search."""
        self._data.setdefault("retrieval", {})["top_k"] = value

    @score_threshold.setter
    def score_threshold(self, value: float):
        """Set the minimum similarity score threshold."""
        self._data.setdefault("retrieval", {})["score_threshold"] = value

    @hybrid_search.setter
    def hybrid_search(self, value: bool):
        """Set whether hybrid BM25+vector search is enabled."""
        self._data.setdefault("retrieval", {})["hybrid_search"] = value

    @bm25_weight.setter
    def bm25_weight(self, value: float):
        """Set the BM25 weight in hybrid search."""
        self._data.setdefault("retrieval", {})["bm25_weight"] = value

    @property
    def intelligent_search_enabled(self) -> bool:
        """Return whether LLM-powered query enhancement is enabled."""
        return self._data.get("retrieval", {}).get(
            "intelligent_search", {}
        ).get("enabled", False)

    @intelligent_search_enabled.setter
    def intelligent_search_enabled(self, value: bool):
        """Enable or disable intelligent search."""
        retrieval = self._data.setdefault("retrieval", {})
        retrieval.setdefault("intelligent_search", {})["enabled"] = value

    @property
    def intelligent_search_extract_keywords(self) -> bool:
        """Return whether to extract keywords in intelligent search."""
        return self._data.get("retrieval", {}).get(
            "intelligent_search", {}
        ).get("extract_keywords", True)

    @property
    def intelligent_search_expand_acronyms(self) -> bool:
        """Return whether to expand acronyms in intelligent search."""
        return self._data.get("retrieval", {}).get(
            "intelligent_search", {}
        ).get("expand_acronyms", True)
