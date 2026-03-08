"""Service layer for knowledge graph computation.

Computes document similarity, clustering, and word clouds from
chunk embeddings stored in ChromaDB.
"""

import logging
import re
from collections import defaultdict
from itertools import combinations

import numpy as np

try:
    from sklearn.cluster import DBSCAN
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:
    DBSCAN = None  # type: ignore[assignment,misc]
    TfidfVectorizer = None  # type: ignore[assignment,misc]

from app.storage.vectorstore import VectorStore

logger = logging.getLogger(__name__)

# Regex to filter code-like tokens from word clouds
_CODE_TOKEN_RE = re.compile(r"^[a-z]{1,2}$|[^a-zA-Z]")


def compute_graph(
    store: VectorStore,
    source_roots: list[str] | None = None,
    top_k: int = 3,
    max_terms: int = 30,
) -> dict:
    """Compute the full knowledge graph from chunk embeddings.

    Args:
        store: VectorStore instance to read from.
        source_roots: Optional scope filter (list of source_root paths).
        top_k: Number of top chunk pairs to average for doc similarity.
        max_terms: Max terms per word cloud.

    Returns dict with keys: nodes, edges, clusters, global_word_cloud, stats.
    """
    raw = store.get_all_with_embeddings(source_roots)
    if not raw["ids"]:
        return _empty_graph()

    # Group chunks by source_path (document)
    docs: dict[str, dict] = defaultdict(lambda: {
        "chunks": [], "embeddings": [], "texts": [],
        "meta": None, "tags": [], "headings": set(),
    })

    for i, chunk_id in enumerate(raw["ids"]):
        meta = raw["metadatas"][i]
        path = meta.get("source_path", chunk_id)
        doc = docs[path]
        doc["embeddings"].append(raw["embeddings"][i])
        doc["texts"].append(raw["documents"][i] or "")
        if doc["meta"] is None:
            doc["meta"] = meta
        # Collect tags
        tag_str = meta.get("tags", "")
        if tag_str and not doc["tags"]:
            doc["tags"] = [t.strip() for t in tag_str.split(",") if t.strip()]
        heading = meta.get("heading", "")
        if heading:
            doc["headings"].add(heading)

    doc_paths = list(docs.keys())
    n_docs = len(doc_paths)

    if n_docs == 0:
        return _empty_graph()

    # Compute mean embedding per document
    doc_mean_embeddings = {}
    for path in doc_paths:
        embs = np.array(docs[path]["embeddings"], dtype=np.float32)
        doc_mean_embeddings[path] = embs.mean(axis=0)

    # Pairwise doc similarity using top-K mean of chunk pairs
    edges = []
    if n_docs >= 2:
        for path_a, path_b in combinations(doc_paths, 2):
            embs_a = np.array(docs[path_a]["embeddings"], dtype=np.float32)
            embs_b = np.array(docs[path_b]["embeddings"], dtype=np.float32)
            # Dot product matrix (embeddings are L2-normalized, so dot = cosine sim)
            sim_matrix = embs_a @ embs_b.T
            # Flatten and take top-K
            flat = sim_matrix.flatten()
            k = min(top_k, len(flat))
            top_indices = np.argpartition(flat, -k)[-k:]
            weight = float(flat[top_indices].mean())

            # Build top chunk pair previews
            top_pairs = []
            for idx in np.argsort(flat)[-min(3, len(flat)):]:
                idx_a, idx_b = divmod(int(idx), sim_matrix.shape[1])
                top_pairs.append({
                    "source_text": _truncate(docs[path_a]["texts"][idx_a], 120),
                    "target_text": _truncate(docs[path_b]["texts"][idx_b], 120),
                    "similarity": round(float(flat[idx]), 3),
                })

            edges.append({
                "source": path_a,
                "target": path_b,
                "weight": round(weight, 4),
                "top_chunk_pairs": top_pairs,
            })

    # DBSCAN clustering on mean doc embeddings
    cluster_labels = _cluster_docs(doc_paths, doc_mean_embeddings)

    # Build cluster groups
    cluster_docs: dict[int, list[str]] = defaultdict(list)
    for path, cid in zip(doc_paths, cluster_labels):
        cluster_docs[cid].append(path)

    # Word clouds per cluster, per doc, and global
    all_texts = []
    doc_text_map: dict[str, str] = {}
    for path in doc_paths:
        combined = " ".join(docs[path]["texts"])
        doc_text_map[path] = combined
        all_texts.append(combined)

    global_word_cloud = _extract_word_cloud(all_texts, max_terms)

    clusters = []
    for cid in sorted(cluster_docs.keys()):
        cluster_texts = [doc_text_map[p] for p in cluster_docs[cid]]
        clusters.append({
            "id": cid,
            "label": f"Cluster {cid}" if cid >= 0 else "Unclustered",
            "doc_count": len(cluster_docs[cid]),
            "word_cloud": _extract_word_cloud(cluster_texts, max_terms),
        })

    # Build nodes
    nodes = []
    for i, path in enumerate(doc_paths):
        meta = docs[path]["meta"] or {}
        title = meta.get("title", "") or path.rsplit("/", 1)[-1]
        nodes.append({
            "id": path,
            "label": title,
            "cluster_id": int(cluster_labels[i]),
            "chunk_count": len(docs[path]["embeddings"]),
            "source_root": meta.get("source_root", ""),
            "tags": docs[path]["tags"],
            "headings": sorted(docs[path]["headings"]),
            "word_cloud": _extract_word_cloud([doc_text_map[path]], max_terms),
        })

    total_chunks = sum(len(docs[p]["embeddings"]) for p in doc_paths)

    return {
        "nodes": nodes,
        "edges": edges,
        "clusters": clusters,
        "global_word_cloud": global_word_cloud,
        "stats": {
            "doc_count": n_docs,
            "chunk_count": total_chunks,
            "edge_count": len(edges),
        },
    }


def _cluster_docs(
    doc_paths: list[str],
    doc_mean_embeddings: dict[str, np.ndarray],
) -> list[int]:
    """Run DBSCAN clustering on mean doc embeddings."""
    n = len(doc_paths)
    if n < 3 or DBSCAN is None:
        # Fallback: all in cluster 0
        return [0] * n

    X = np.array([doc_mean_embeddings[p] for p in doc_paths], dtype=np.float32)
    try:
        clusterer = DBSCAN(eps=0.5, min_samples=2, metric="cosine")
        labels = clusterer.fit_predict(X)
        return [int(l) for l in labels]
    except Exception as e:
        logger.warning("DBSCAN clustering failed, falling back: %s", e)
        return [0] * n


def _extract_word_cloud(texts: list[str], max_terms: int = 30) -> dict[str, float]:
    """Extract weighted terms from texts using TF-IDF."""
    if not texts or TfidfVectorizer is None:
        return {}

    joined = [t for t in texts if t.strip()]
    if not joined:
        return {}

    try:
        vectorizer = TfidfVectorizer(
            max_features=max_terms * 3,
            stop_words="english",
            token_pattern=r"(?u)\b[a-zA-Z]{3,}\b",
            max_df=0.9,
            min_df=1,
        )
        tfidf_matrix = vectorizer.fit_transform(joined)
        feature_names = vectorizer.get_feature_names_out()
        # Average TF-IDF scores across documents
        scores = tfidf_matrix.mean(axis=0).A1
        # Sort and take top terms
        top_indices = scores.argsort()[-max_terms:][::-1]
        result = {}
        for idx in top_indices:
            term = feature_names[idx]
            if not _CODE_TOKEN_RE.match(term) and scores[idx] > 0:
                result[term] = round(float(scores[idx]), 4)
        return result
    except Exception as e:
        logger.warning("TF-IDF extraction failed: %s", e)
        return {}


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def _empty_graph() -> dict:
    """Return an empty graph structure."""
    return {
        "nodes": [],
        "edges": [],
        "clusters": [],
        "global_word_cloud": {},
        "stats": {"doc_count": 0, "chunk_count": 0, "edge_count": 0},
    }
