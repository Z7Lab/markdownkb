# Doc Map

The Doc Map is an interactive 3D visualization of how your documents relate to each other by content similarity. Documents appear as colored nodes, with edges connecting similar documents. Clusters of related documents share colors. Word clouds show the key terms for selected documents or the entire collection.

Requires the `docmap` plugin (enabled by default) and WebGL in the browser.

## How It Works

### Computing Similarity

When you open the Doc Map or click Refresh:

1. **Load embeddings** — every chunk's vector embedding is read from ChromaDB
2. **Group by document** — chunks are grouped by source file, and a mean embedding is computed per document
3. **Pairwise comparison** — for every pair of documents, the top-K most similar chunk pairs are found (using cosine similarity on the raw chunk vectors, not the mean). The average of these top-K scores becomes the edge weight between those documents
4. **Edge filtering** — edges below the minimum weight threshold (0.6 by default) are dropped server-side before sending to the browser
5. **Clustering** — DBSCAN groups documents by similarity in embedding space, with an auto-tuned epsilon based on the pairwise distance distribution
6. **Word clouds** — TF-IDF extracts the most distinctive terms per document, per cluster, and globally

The top-K approach (default K=3) means similarity is measured by the best chunk-to-chunk matches, not just the overall document averages. Two documents that share a highly similar section will have a strong edge even if the rest of their content is unrelated.

### The 3D Graph

Documents are laid out using a force-directed simulation (d3-force-3d):

- **Nodes** = documents, sized by chunk count
- **Edges** = similarity connections, thicker for higher similarity
- **Colors** = cluster membership (DBSCAN). Unclustered documents are gray
- **Layout** = the force simulation pulls connected nodes together and pushes unconnected ones apart

## Sidebar Controls

### Similarity Threshold (slider: 0.60 – 0.95)

Controls which edges are visible. Only edges with a similarity score at or above this threshold are drawn. Nodes without any visible edges are hidden — except bucket nodes, which always render so a selected bucket is never invisible.

- **Lower threshold (0.60)** — shows more connections, including weaker similarities. The graph is denser, more documents visible.
- **Higher threshold (0.85+)** — shows only strong connections. The graph is sparser, only highly similar documents are linked.

This is a client-side filter — it doesn't refetch data, just hides/shows edges and nodes from the data already loaded. Adjusting it is instant and doesn't recenter the camera.

Hover the info icon next to the label for an in-app reminder of what the slider controls.

### Spread (slider: 10% – 200%)

Controls the spacing between nodes in the force simulation. This is purely visual — it doesn't change which documents are connected, just how far apart they're drawn.

- **Low spread (10–50%)** — nodes cluster tightly together. Good for seeing overall structure.
- **Default spread (100%)** — balanced spacing.
- **High spread (150–200%)** — nodes spread far apart. Good for reading labels on individual nodes.

Changing spread reheats the physics simulation so nodes reposition smoothly.

### Bucket Strength (slider: 0.00 – 1.00, only visible with a bucket selected)

Controls which bucket-to-scope edges are drawn. The scale is a **normalized fused rank** — each bucket document's best scope match is weight 1.00, its worst match is 0.00, everything in between scales linearly. Default is 0.50.

- **1.00** — only each bucket doc's single strongest scope match
- **0.50** (default) — roughly the top half of each bucket doc's scope matches
- **0.00** — every computed connection, including the weakest ones

This is a server-side filter and re-triggers a fused-rank build when you pass a 0.05 step. Slider drags are debounced (~300ms) so quick scrubbing doesn't spawn a storm of parallel compute jobs. Different values produce different cache entries; flipping back to a previous value is instant on the second visit.

The "fused rank" itself is not a cosine similarity — see *Bucket Overlay* below for how it's computed and why it exists.

### Filter by Term

Type a term to highlight matching documents. The search checks document labels, tags, headings, and word cloud terms. Matching nodes are highlighted, non-matching nodes are dimmed.

### Word Clouds Toggle

Enables or disables word cloud computation. When on:

- The sidebar shows a word cloud below the controls
- By default it shows global terms (across all visible documents)
- Clicking a node shows that document's specific terms
- Searching shows merged terms from matching documents

Word clouds use TF-IDF (term frequency–inverse document frequency) to find distinctive terms — words that appear frequently in the selected documents but rarely across the whole collection. Common words like "the" or "document" are filtered out.

Turning word clouds off and back on triggers a data refetch (the server computes them as part of the graph data).

### Scope and Tag Filters

The scope and tag filters at the top of the sidebar work the same as on other tabs — select a scope to limit the doc map to documents in those folders/tags, with exclude patterns applied. Changing scopes triggers a full recomputation.

### Refresh

Re-computes the entire doc map from scratch. Use this after indexing new documents or when the "Data may be outdated" warning appears (shown when documents have been re-indexed since the map was built).

## Interaction

- **Click a node** — selects it and highlights its neighborhood. The selected node turns yellow, its connected neighbors keep their cluster colors, and everything else dims. This isolates one document's relationships so you can see exactly what it's similar to without the rest of the graph distracting.
- **Click an edge** — shows a chunk-level similarity detail panel between the two documents: which specific chunks are most similar, with text previews and similarity scores. This shows you *why* two documents are connected.
- **Click the background** — clears all selection and highlighting, returns to the full graph view
- **Click a word cloud term** — highlights all documents that contain that term across their content, tags, and headings
- **Mouse drag** — rotate the 3D view
- **Scroll** — zoom in/out
- **Zoom controls** (bottom-right) — zoom in, zoom out, re-center

## Library

The 3D visualization is built with [react-force-graph-3d](https://github.com/vasturiano/react-force-graph), which wraps Three.js and d3-force-3d. The force simulation handles layout (attraction between connected nodes, repulsion between all nodes), and Three.js handles the WebGL rendering. This requires a browser with WebGL support — if WebGL is unavailable (e.g. remote desktop without GPU passthrough), the tab shows a fallback message.

## Stats Bar

The top-left corner shows: `X/Y docs · Z edges` — how many documents have visible connections (X) out of total documents in the data (Y), and how many edges are shown at the current threshold.

## Staleness Indicator

When documents have been re-indexed after the doc map was built, a yellow "Data may be outdated" banner appears with a Refresh button. The doc map caches its data in memory — it doesn't automatically rebuild when files change.

## Using Scopes for Focused Exploration

With all sources visible, a large knowledge base produces a dense graph where everything connects to everything — it's hard to see structure. Scopes let you filter the doc map down to a focused subset:

**Research workflow:** Select a scope like "Project Docs" to see only project documentation. The graph now shows how your projects relate to each other — which ones cover similar ground, which are isolated. Add an exclude pattern like `agent-reviewed-*` to remove templated files that add noise without meaningful content.

**Finding hidden connections:** Scope to a tag like "architecture" to see only architecture documents across all projects. Documents that cover similar architectural patterns cluster together even if they're in different project folders. This surfaces connections you wouldn't find by browsing directories.

**Comparing topics:** Select two scopes at once (multi-select) to see how two different document collections relate. Documents from both scopes appear in the same graph — edges between them show where the collections overlap in content.

**Narrowing with the threshold:** Start with a low similarity threshold (0.60) to see the broad structure, then raise it (0.80+) to see only the strongest connections. The weak edges disappear and the core clusters become clear.

The combination of scoping (which documents to include) and thresholding (which connections to show) lets you go from "all 900 documents" to "the 12 infrastructure docs with strong similarity to each other" in two interactions.

## Bucket Overlay

When a bucket is selected alongside a scope (or "All sources"), the Doc Map visualizes both your permanent documents and the bucket's documents in the same graph.

### How It Works Technically

The backend computes three sets of edges:

1. **Main-to-main edges** — pairwise similarity between your permanent documents (filtered by scope), using the mean of top-K chunk-pair cosine similarities
2. **Bucket-to-bucket edges** — pairwise similarity within the bucket's documents (same metric)
3. **Cross-collection edges** — bucket-to-scope overlap, computed via **Reciprocal Rank Fusion** of four signals (described below)

Bucket nodes always render even if they have zero surviving edges — selecting a bucket should never make it invisible.

#### Why cross-collection edges are different

Earlier versions used a single hardcoded similarity floor (0.75) for bucket-to-scope edges. In practice, thematic overlap between a bucket and a scope usually lives in a narrower, lower similarity band (~0.55–0.70) than intra-scope overlap, so the fixed floor was either too strict (bucket nodes floated orphaned) or too permissive (bucket nodes became hairball hubs). Worse, embedding similarity alone has a "plateau problem" — for a tight scope, every scope doc ends up at almost the same similarity to the bucket, making the ranking meaningless.

To address both, cross-collection edges now fuse four independent similarity signals:

1. **Mean top-K chunk-pair cosine** — the baseline embedding-similarity measure, the same one used for main-to-main edges. Captures overall thematic overlap.
2. **Max chunk-pair cosine** — the single strongest chunk-to-chunk match. Captures "these docs have one very strongly related passage," which the mean smooths away.
3. **TF-IDF cosine** — document-level bag-of-words cosine. Captures *distinctive-vocabulary overlap*, independent of paraphrase. (MarkdownKB's search already does something similar at the chunk level via BM25 — see [retrieval.md](retrieval.md) for the analogous idea in hybrid retrieval.)
4. **Relative neighbour rank** — for each scope doc, how highly the bucket doc ranks among its other neighbours. Captures whether the bucket is close to a doc *relative to that doc's own neighbourhood*, which catches isolated scope docs that would otherwise be hidden by the plateau.

These four signals are fused via **Reciprocal Rank Fusion** (RRF, Cormack et al. 2009): each signal independently ranks the scope docs, then `score(doc) = Σ 1/(60 + rank_signal(doc))` across the four signals. Docs that score well in multiple signals rise to the top; docs that score well in only one (e.g. TF-IDF-only matches from shared boilerplate) get moderated.

The fused score is then **normalized per bucket doc to [0, 1]** so each bucket doc's best scope match is always weight 1.00 and its worst is 0.00. This is what the Bucket Strength slider filters — a value of 0.5 keeps the top half of each bucket doc's ranked scope matches; 1.0 keeps only the single best.

An empirical comparison of these four signals against the baseline-only approach, including why RRF was chosen over a weighted blend, is archived under `project_artifacts/mdkb/experiments/docmap-edge-weight-strategies.md` in the internal `dev-resources` repository.

### Visual Distinction

- **Permanent document nodes** — colored by cluster (DBSCAN clustering based on embedding similarity)
- **Bucket nodes** — colored using the bucket's assigned color (red by default) and rendered larger (3x base size) so they're immediately identifiable among hundreds of permanent nodes
- **Cross-collection edges** — same visual treatment as other edges, but they connect bucket-colored nodes to cluster-colored nodes, making the overlap pattern visible

### What the Overlay Reveals

When bucket nodes cluster **near** specific permanent nodes, those documents cover similar ground. When bucket nodes cluster **far** from everything, the bucket contains topics not covered in your existing knowledge base.

Use cases:

- **Evaluating new material** — load vendor docs into a bucket, overlay with your architecture scope, and see which vendor concepts cluster near your existing patterns
- **Research discovery** — import conference notes or papers as a bucket, overlay with your research scope, and find where new ideas connect to your existing work
- **Gap analysis** — if bucket nodes float disconnected or cluster alone, those topics are gaps in your permanent knowledge base
- **Overlap detection** — if bucket nodes sit right on top of existing clusters, you already have that knowledge documented — the bucket content is redundant

## How It Differs from Knowledge Graph

- **Doc Map** shows **document-to-document similarity** computed from embeddings. Edges mean "these documents have similar content." No LLM involved.
- **Knowledge Graph** shows **entities and typed relationships** extracted by the LLM. Edges mean "concept A relates to concept B" with a named relationship type.

Doc Map answers: "which documents cover similar topics?" Knowledge Graph answers: "what concepts exist and how are they connected?"

## Configuration

```yaml
plugins:
  docmap:
    enabled: true
```

No additional configuration — the doc map uses the same embedding model and indexed data as search and chat. The minimum edge weight (0.6) and adaptive edge limit (~10 edges per document) are hardcoded in the graph computation service.

## Implementation

| File | Purpose |
|------|---------|
| `app/services/graph_service.py` | Pairwise similarity, DBSCAN clustering, TF-IDF word clouds |
| `app/plugins/docmap/router.py` | API endpoints, in-memory caching, scope filtering |
| `frontend/src/components/visualization/visualization-tab.tsx` | 3D rendering, controls, interaction |
| `frontend/src/hooks/use-visualization.ts` | Data fetching, progress polling, state management |
