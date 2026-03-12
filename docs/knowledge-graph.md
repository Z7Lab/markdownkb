# Knowledge Graph

The Graph tab visualizes relationships between indexed documents as an interactive 3D force-directed graph. Documents are nodes, and edges represent semantic similarity between them.

## How It Works

### Similarity Computation

1. **Load embeddings** — All chunk embeddings are fetched from ChromaDB and grouped by source document.
2. **Mean embeddings** — Each document gets a mean embedding (average of its chunk vectors) used for clustering.
3. **Pairwise similarity** — For every pair of documents, the top-K most similar chunk pairs are found (using cosine similarity via dot product on L2-normalized vectors). The edge weight is the mean of those top-K scores.
4. **Edge filtering** — Edges below the server-side `min_weight` threshold (default 0.6) are discarded. If too many edges remain, adaptive filtering caps the total at ~10 edges per document, keeping only the strongest connections.

### Why top-K chunk pairs instead of mean embeddings?

Mean embeddings lose detail. Two documents might share a highly relevant section buried among unrelated content — the mean would wash it out. By comparing individual chunk pairs and averaging the top-K, we capture the strongest topical overlaps even when documents are otherwise dissimilar.

### Adaptive Edge Capping

Different embedding models produce different similarity distributions. Dense models like BGE cluster tighter than sparser models like MiniLM, so a fixed threshold can produce either too many or too few edges.

The adaptive cap works as follows:

- Maximum edges = `max(num_docs * 10, 2000)`
- If the number of edges exceeding `min_weight` is greater than this limit, only the top edges by weight are kept
- This means the effective minimum weight adjusts automatically based on the embedding model

With BGE and ~800 documents, this typically produces 5,000–8,000 edges (down from 300K+ without the cap).

## Clustering

Documents are grouped into clusters using DBSCAN on mean embeddings with cosine distance.

### Auto-tuned eps

DBSCAN's `eps` parameter (neighborhood radius) is chosen automatically:

1. Compute all pairwise cosine distances between mean document embeddings
2. Set `eps` to the 15th percentile of that distribution
3. Clamp to the range [0.05, 0.5]

This means only the most similar ~15% of document pairs are considered "neighbors" for clustering purposes. The algorithm adapts to whatever embedding model is active — tighter embedding spaces get a smaller eps, looser ones get a larger eps.

## Word Clouds

Each node, cluster, and the global graph get a word cloud extracted via TF-IDF:

- **Global**: TF-IDF across all document texts
- **Per-cluster**: TF-IDF across documents in that cluster
- **Per-document**: TF-IDF on that single document's text

Terms are filtered to English words (3+ characters), excluding stop words and code-like tokens.

## Frontend Controls

### Similarity Threshold (slider)

Client-side filter on top of the server-side `min_weight`. The slider range is 0.60–0.95 with a default of 0.75. Raising the threshold removes weaker edges and disconnected nodes, revealing only the strongest document relationships.

- **Low (0.60)**: Shows more connections, useful for exploring loose relationships
- **High (0.90+)**: Shows only very strong connections, highlights document clusters

### Spread

Controls the physical spacing of the force simulation. Higher values push nodes further apart; lower values create a more compact layout.

### Search / Filter

Type a term to highlight nodes whose label, tags, headings, or word cloud contain the term. Combined with scope and tag filters from the sidebar.

## Caching

Graph computation is expensive (O(n^2) pairwise comparisons). Results are cached in-memory on the server, keyed by:

- Source roots (scope filter)
- Tags (scope tags + ad-hoc tags)
- top_k, word_clouds, min_weight parameters

The cache is automatically invalidated when documents are indexed or deleted (via the IndexEventBus).

## Performance Characteristics

| Documents | Pairs | Typical compute time | Notes |
|-----------|-------|---------------------|-------|
| 100 | 4,950 | ~2s | Fast, no issues |
| 500 | 124,750 | ~30s | Noticeable wait, progress bar shown |
| 800 | 322,000 | ~60–90s | Progress polling active |
| 1000+ | 500,000+ | 2–5min | Consider using scope filters to reduce |

Tips for large collections:
- Use **scope filters** to graph a subset of documents
- Disable **word clouds** to skip TF-IDF extraction (~20% faster)
- The similarity slider is client-side only — it doesn't trigger recomputation
