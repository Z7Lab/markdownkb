"""Hybrid retriever combining vector similarity with BM25 keyword search."""

import logging
from dataclasses import dataclass

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None
    logging.getLogger(__name__).warning(
        "rank_bm25 not installed — hybrid search will use vector-only mode"
    )

from app.config import Settings
from app.embeddings.embedder import embed_query
from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result with document content, metadata, and score."""

    document: str
    metadata: dict
    score: float


class Retriever:
    """Combines vector similarity search with optional BM25 reranking."""

    def __init__(self, store: VectorStore,
                 settings: Settings | None = None,
                 tracking: TrackingDB | None = None):
        self._store = store
        self._settings = settings or Settings.get()
        self._tracking = tracking

    @property
    def store(self) -> VectorStore:
        """Public access to the underlying vector store."""
        return self._store

    def search(self, query: str, top_k: int | None = None,
               folders_filter: list[str] | None = None,
               scope_tags: list[str] | None = None,
               allowed_paths: set[str] | None = None) -> list[SearchResult]:
        """Search using vector similarity and optional BM25.

        Args:
            folders_filter: Multiple folder paths (used by scope filtering).
                            Uses ChromaDB ``$in`` operator.
            scope_tags: Tags from a scope definition (ChromaDB metadata).
            allowed_paths: Pre-resolved file paths from tracking DB tags.
        """
        k = top_k or self._settings.top_k

        if self._store.count == 0:
            return []

        # Vector search
        query_embedding = embed_query(query, self._settings.embedding_model, remote_config=self._settings.embedding_remote_config)

        where = None
        if folders_filter and len(folders_filter) == 1:
            where = {"source_root": folders_filter[0]}
        elif folders_filter and len(folders_filter) > 1:
            where = {"source_root": {"$in": folders_filter}}

        vector_results = self._store.query(
            query_embedding, n_results=k * 2, where=where
        )

        results: list[SearchResult] = []
        for doc, meta, dist in zip(
            vector_results["documents"],
            vector_results["metadatas"],
            vector_results["distances"],
        ):
            score = 1 - dist  # cosine distance -> similarity
            results.append(SearchResult(
                document=doc, metadata=meta, score=score
            ))

        # Hybrid search with BM25 if enabled
        if self._settings.hybrid_search:
            results = self._apply_bm25_rerank(query, results)

        # Apply scope tags filter (match any scope tag — OR logic, exact match)
        if scope_tags:
            scope_tag_set = set(scope_tags)
            def _has_scope_tag(meta_tags: str) -> bool:
                file_tags = {t.strip() for t in meta_tags.split(",") if t.strip()}
                return bool(scope_tag_set & file_tags)
            results = [r for r in results if _has_scope_tag(r.metadata.get("tags", ""))]

        # Apply allowed_paths filter (from tracking DB tag resolution)
        if allowed_paths is not None:
            results = [
                r for r in results
                if r.metadata.get("source_path", "") in allowed_paths
            ]

        # Exclude files where include_rag is toggled off
        if self._tracking:
            excluded = self._tracking.get_rag_excluded_paths()
            if excluded:
                results = [
                    r for r in results
                    if r.metadata.get("source_path") not in excluded
                ]

        # Filter by threshold and limit
        threshold = self._settings.score_threshold
        pre_filter_count = len(results)
        pre_filter_top = max((r.score for r in results), default=0.0)
        results = [r for r in results if r.score >= threshold]
        results.sort(key=lambda r: r.score, reverse=True)

        if pre_filter_count > len(results):
            logger.info(
                "Filtered %d/%d results below threshold %.2f "
                "(pre-filter top: %.3f, post-filter top: %.3f)",
                pre_filter_count - len(results), pre_filter_count, threshold,
                pre_filter_top, results[0].score if results else 0.0,
            )

        return results[:k]

    def _apply_bm25_rerank(
        self, query: str,
        vector_results: list[SearchResult],
    ) -> list[SearchResult]:
        """Rerank vector search results using BM25 keyword scoring."""
        if BM25Okapi is None or not vector_results:
            return vector_results

        corpus = [r.document.lower().split() for r in vector_results]
        bm25 = BM25Okapi(corpus)
        query_tokens = query.lower().split()
        bm25_scores = bm25.get_scores(query_tokens)

        # Clamp negative BM25 scores to zero — BM25Okapi computes IDF on
        # the small retrieved corpus, so common query terms get negative IDF
        # which can drag combined scores below threshold.  BM25 should only
        # boost keyword matches, never penalize their absence.
        bm25_scores = [max(0.0, s) for s in bm25_scores]

        # Normalize BM25 scores
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1.0
        bm25_weight = self._settings.bm25_weight
        vector_weight = 1 - bm25_weight

        for i, result in enumerate(vector_results):
            normalized_bm25 = bm25_scores[i] / max_bm25
            result.score = (
                vector_weight * result.score
                + bm25_weight * normalized_bm25
            )

        return vector_results

    def get_all_metadatas(self) -> list[dict]:
        """Return all chunk metadata from the store."""
        return self._store.get_all_metadatas()

    def get_unique_sources(self) -> list[str]:
        """Return sorted list of unique source file paths."""
        metadatas = self._store.get_all_metadatas()
        sources = set()
        for m in metadatas:
            if "source_path" in m:
                sources.add(m["source_path"])
        return sorted(sources)

    def get_unique_folders(self) -> list[str]:
        """Return sorted list of unique source root directories."""
        metadatas = self._store.get_all_metadatas()
        folders = set()
        for m in metadatas:
            if "source_root" in m:
                folders.add(m["source_root"])
        return sorted(folders)

    def get_unique_tags(self) -> list[str]:
        """Return sorted list of unique tags across all chunks."""
        metadatas = self._store.get_all_metadatas()
        tags = set()
        for m in metadatas:
            tag_str = m.get("tags", "")
            if tag_str:
                for t in tag_str.split(", "):
                    if t.strip():
                        tags.add(t.strip())
        return sorted(tags)
