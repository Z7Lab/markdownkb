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

# Progress tracking for graph computation
graph_progress: dict[str, float | str] = {
    "fraction": 0.0,
    "phase": "idle",
}


def compute_graph(
    store: VectorStore,
    source_roots: list[str] | None = None,
    top_k: int = 3,
    max_terms: int = 30,
    word_clouds: bool = True,
    min_weight: float = 0.0,
    allowed_paths: set[str] | None = None,
) -> dict:
    """Compute the full knowledge graph from chunk embeddings.

    Args:
        store: VectorStore instance to read from.
        source_roots: Optional scope filter (list of source_root paths).
        top_k: Number of top chunk pairs to average for doc similarity.
        max_terms: Max terms per word cloud.
        min_weight: Minimum edge weight to include (filters weak edges).
        allowed_paths: Optional set of file paths to include (for tag-based filtering).

    Returns dict with keys: nodes, edges, clusters, global_word_cloud, stats.
    """
    def progress(frac: float, phase: str):
        graph_progress["fraction"] = frac
        graph_progress["phase"] = phase

    progress(0.0, "Loading embeddings...")
    raw = store.get_all_with_embeddings(source_roots)
    if not raw["ids"]:
        progress(1.0, "idle")
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

    # Path-based filtering: keep only documents in the allowed set
    if allowed_paths is not None:
        docs = {
            path: doc for path, doc in docs.items()
            if path in allowed_paths
        }

    doc_paths = list(docs.keys())
    n_docs = len(doc_paths)

    if n_docs == 0:
        progress(1.0, "idle")
        return _empty_graph()

    progress(0.1, f"Computing embeddings for {n_docs} documents...")
    # Pre-compute embedding arrays and mean embeddings once
    doc_emb_arrays: dict[str, np.ndarray] = {}
    doc_mean_embeddings = {}
    for path in doc_paths:
        embs = np.array(docs[path]["embeddings"], dtype=np.float32)
        doc_emb_arrays[path] = embs
        doc_mean_embeddings[path] = embs.mean(axis=0)

    # Pairwise doc similarity using top-K mean of chunk pairs
    n_pairs = n_docs * (n_docs - 1) // 2
    progress(0.15, f"Computing {n_pairs:,} pairwise similarities...")
    edges = []
    pair_count = 0
    if n_docs >= 2:
        for path_a, path_b in combinations(doc_paths, 2):
            embs_a = doc_emb_arrays[path_a]
            embs_b = doc_emb_arrays[path_b]
            # Dot product matrix (embeddings are L2-normalized, so dot = cosine sim)
            sim_matrix = embs_a @ embs_b.T
            # Flatten and take top-K
            flat = sim_matrix.flatten()
            k = min(top_k, len(flat))
            top_indices = np.argpartition(flat, -k)[-k:]
            weight = float(flat[top_indices].mean())

            if weight >= min_weight:
                edges.append({
                    "source": path_a,
                    "target": path_b,
                    "weight": round(weight, 4),
                })
            pair_count += 1
            if pair_count % 500 == 0:
                frac = 0.15 + 0.55 * (pair_count / max(n_pairs, 1))
                progress(frac, f"Similarities: {pair_count:,}/{n_pairs:,} pairs...")

    progress(0.7, "Clustering documents...")
    # DBSCAN clustering on mean doc embeddings
    cluster_labels = _cluster_docs(doc_paths, doc_mean_embeddings)

    # Build cluster groups
    cluster_docs: dict[int, list[str]] = defaultdict(list)
    for path, cid in zip(doc_paths, cluster_labels):
        cluster_docs[cid].append(path)

    # Word clouds per cluster, per doc, and global
    global_word_cloud: dict[str, float] = {}
    doc_word_clouds: dict[str, dict[str, float]] = {}

    if word_clouds:
        all_texts = []
        doc_text_map: dict[str, str] = {}
        for path in doc_paths:
            combined = " ".join(docs[path]["texts"])
            doc_text_map[path] = combined
            all_texts.append(combined)

        progress(0.8, "Extracting word clouds...")
        global_word_cloud = _extract_word_cloud(all_texts, max_terms)

        for path in doc_paths:
            doc_word_clouds[path] = _extract_word_cloud([doc_text_map[path]], max_terms)
    else:
        doc_text_map = {}

    clusters = []
    for cid in sorted(cluster_docs.keys()):
        cluster_wc: dict[str, float] = {}
        if word_clouds:
            cluster_texts = [doc_text_map[p] for p in cluster_docs[cid]]
            cluster_wc = _extract_word_cloud(cluster_texts, max_terms)
        clusters.append({
            "id": cid,
            "label": f"Cluster {cid}" if cid >= 0 else "Unclustered",
            "doc_count": len(cluster_docs[cid]),
            "word_cloud": cluster_wc,
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
            "word_cloud": doc_word_clouds.get(path, {}),
        })

    progress(0.95, "Finalizing graph...")
    total_chunks = sum(len(docs[p]["embeddings"]) for p in doc_paths)

    progress(1.0, "idle")
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


def compute_edge_detail(
    store: VectorStore,
    source: str,
    target: str,
    top_k: int = 5,
) -> dict:
    """Compute chunk-level similarity detail for a single document pair.

    Returns the top-K most similar chunk pairs between the two documents,
    with text previews and similarity scores.
    """
    src_data = store.get_chunks_for_doc(source)
    tgt_data = store.get_chunks_for_doc(target)

    source_texts = [d or "" for d in (src_data.get("documents") or [])]
    target_texts = [d or "" for d in (tgt_data.get("documents") or [])]
    source_embs = src_data.get("embeddings")
    target_embs = tgt_data.get("embeddings")

    if source_embs is None or target_embs is None or len(source_embs) == 0 or len(target_embs) == 0:
        return {"source": source, "target": target, "source_chunks": 0, "target_chunks": 0, "pairs": []}

    embs_a = np.array(source_embs, dtype=np.float32)
    embs_b = np.array(target_embs, dtype=np.float32)
    sim_matrix = embs_a @ embs_b.T
    flat = sim_matrix.flatten()

    k = min(top_k, len(flat))
    top_indices = np.argsort(flat)[-k:][::-1]

    pairs = []
    for idx in top_indices:
        idx_a, idx_b = divmod(int(idx), sim_matrix.shape[1])
        pairs.append({
            "source_text": source_texts[idx_a][:300],
            "target_text": target_texts[idx_b][:300],
            "similarity": round(float(flat[idx]), 4),
        })

    return {
        "source": source,
        "target": target,
        "source_chunks": len(source_embs),
        "target_chunks": len(target_embs),
        "pairs": pairs,
    }


def _empty_graph() -> dict:
    """Return an empty graph structure."""
    return {
        "nodes": [],
        "edges": [],
        "clusters": [],
        "global_word_cloud": {},
        "stats": {"doc_count": 0, "chunk_count": 0, "edge_count": 0},
    }
