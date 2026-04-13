"""Service layer for knowledge graph computation.

Computes document similarity, clustering, and word clouds from
chunk embeddings stored in ChromaDB.
"""

import logging
import re
from collections import defaultdict
from itertools import combinations

import numpy as np

_SKLEARN_AVAILABLE = True
try:
    from sklearn.cluster import DBSCAN
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:
    _SKLEARN_AVAILABLE = False
    DBSCAN = None  # type: ignore[assignment,misc]  # optional dep, checked at call site
    TfidfVectorizer = None  # type: ignore[assignment,misc]  # optional dep, checked at call site
    logging.getLogger(__name__).warning(
        "scikit-learn not installed — graph clustering and word clouds will be degraded"
    )

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
    excluded_paths: set[str] | None = None,
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

    # Exclude files where include_rag is false
    if excluded_paths:
        docs = {
            path: doc for path, doc in docs.items()
            if path not in excluded_paths
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
    all_weights: list[tuple[str, str, float]] = []
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
                all_weights.append((path_a, path_b, weight))
            pair_count += 1
            if pair_count % 500 == 0:
                frac = 0.15 + 0.55 * (pair_count / max(n_pairs, 1))
                progress(frac, f"Similarities: {pair_count:,}/{n_pairs:,} pairs...")

    # Adaptive filtering: if too many edges, raise the effective threshold
    # to keep at most ~max_edges (roughly 10 per doc).  This prevents the
    # graph from becoming an unreadable blob with dense embedding models.
    max_edges = max(n_docs * 10, 2000)
    if len(all_weights) > max_edges:
        all_weights.sort(key=lambda t: t[2], reverse=True)
        all_weights = all_weights[:max_edges]

    edges = [
        {"source": s, "target": t, "weight": round(w, 4)}
        for s, t, w in all_weights
    ]

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
    result = {
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
    if not _SKLEARN_AVAILABLE:
        result["degraded"] = True
        result["degraded_reason"] = "scikit-learn not installed — clustering and word clouds unavailable"
    return result


def _cluster_docs(
    doc_paths: list[str],
    doc_mean_embeddings: dict[str, np.ndarray],
) -> list[int]:
    """Run DBSCAN clustering on mean doc embeddings.

    Automatically selects an eps value based on the pairwise cosine distance
    distribution so that clustering works across different embedding models
    (some produce tighter clusters than others).
    """
    n = len(doc_paths)
    if n < 3 or DBSCAN is None:
        # Fallback: all in cluster 0
        return [0] * n

    X = np.array([doc_mean_embeddings[p] for p in doc_paths], dtype=np.float32)
    try:
        # Compute pairwise cosine distances and pick eps at the 15th percentile
        # so only genuinely close documents cluster together.
        from sklearn.metrics.pairwise import cosine_distances
        dists = cosine_distances(X)
        # Upper triangle only (exclude self-distances on diagonal)
        triu = dists[np.triu_indices(n, k=1)]
        eps = float(np.percentile(triu, 15))
        # Clamp to a reasonable range
        eps = max(0.05, min(eps, 0.5))
        logger.debug("DBSCAN auto-eps: %.4f (from %d pairwise distances)", eps, len(triu))

        clusterer = DBSCAN(eps=eps, min_samples=2, metric="cosine")
        labels = clusterer.fit_predict(X)
        return [int(l) for l in labels]
    except (ValueError, RuntimeError, np.linalg.LinAlgError) as e:
        logger.error("DBSCAN clustering failed, marking all docs as unclustered: %s", e)
        return [-1] * n


def _extract_word_cloud(texts: list[str], max_terms: int = 30) -> dict[str, float]:
    """Extract weighted terms from texts using TF-IDF."""
    if not texts or TfidfVectorizer is None:
        return {}

    joined = [t for t in texts if t.strip()]
    if not joined:
        return {}

    try:
        # When only 1 document, max_df must be 1.0 (not 0.9 which rounds to 0)
        effective_max_df: float | int = 0.9 if len(joined) > 1 else 1.0
        vectorizer = TfidfVectorizer(
            max_features=max_terms * 3,
            stop_words="english",
            token_pattern=r"(?u)\b[a-zA-Z]{3,}\b",
            max_df=effective_max_df,
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
    except (ValueError, RuntimeError) as e:
        logger.error("TF-IDF extraction failed: %s", e)
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

    source_docs = src_data.get("documents")
    target_docs = tgt_data.get("documents")
    if not source_docs or not target_docs:
        return {"source": source, "target": target, "source_chunks": 0, "target_chunks": 0, "pairs": []}
    source_texts = [d or "" for d in source_docs]
    target_texts = [d or "" for d in target_docs]
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


def compute_cross_edges(
    store_a: "VectorStore",
    store_b: "VectorStore",
    top_k: int = 3,
    min_weight: float = 0.0,
    allowed_paths_a: set[str] | None = None,
    excluded_paths_a: set[str] | None = None,
    top_n_per_target: int | None = None,
) -> list[dict]:
    """Compute similarity edges between documents in two different stores.

    Used to find connections between bucket documents and main collection
    documents. Returns edges in the same format as compute_graph.

    When ``top_n_per_target`` is set, each target (store_b) document keeps
    only its N strongest edges after ``min_weight`` filtering, preventing
    bucket docs from becoming over-connected hubs.
    """
    raw_a = store_a.get_all_with_embeddings()
    raw_b = store_b.get_all_with_embeddings()

    if not raw_a["ids"] or not raw_b["ids"]:
        return []

    # Group chunks by source_path for each store
    def _group_docs(raw):
        docs = {}
        for i, chunk_id in enumerate(raw["ids"]):
            meta = raw["metadatas"][i]
            path = meta.get("source_path", chunk_id)
            if path not in docs:
                docs[path] = []
            docs[path].append(raw["embeddings"][i])
        return docs

    docs_a = _group_docs(raw_a)
    docs_b = _group_docs(raw_b)

    # Apply path filters to store_a (main collection)
    if allowed_paths_a is not None:
        docs_a = {p: e for p, e in docs_a.items() if p in allowed_paths_a}
    if excluded_paths_a:
        docs_a = {p: e for p, e in docs_a.items() if p not in excluded_paths_a}

    if not docs_a or not docs_b:
        return []

    # Compute cross-collection pairwise similarity
    edges = []
    for path_a, chunks_a in docs_a.items():
        embs_a = np.array(chunks_a, dtype=np.float32)
        for path_b, chunks_b in docs_b.items():
            embs_b = np.array(chunks_b, dtype=np.float32)
            sim_matrix = embs_a @ embs_b.T
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

    if top_n_per_target is not None and top_n_per_target > 0:
        by_target: dict[str, list[dict]] = {}
        for e in edges:
            by_target.setdefault(e["target"], []).append(e)
        kept: list[dict] = []
        for target_edges in by_target.values():
            target_edges.sort(key=lambda x: x["weight"], reverse=True)
            kept.extend(target_edges[:top_n_per_target])
        edges = kept

    return edges


def _empty_graph() -> dict:
    """Return an empty graph structure."""
    return {
        "nodes": [],
        "edges": [],
        "clusters": [],
        "global_word_cloud": {},
        "stats": {"doc_count": 0, "chunk_count": 0, "edge_count": 0},
    }
