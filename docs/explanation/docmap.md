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

Controls which edges are visible. Only edges with a similarity score at or above this threshold are drawn. Nodes without any visible edges are hidden.

- **Lower threshold (0.60)** — shows more connections, including weaker similarities. The graph is denser, more documents visible.
- **Higher threshold (0.85+)** — shows only strong connections. The graph is sparser, only highly similar documents are linked.

This is a client-side filter — it doesn't refetch data, just hides/shows edges and nodes from the data already loaded. Adjusting it is instant and doesn't recenter the camera.

### Spread (slider: 10% – 200%)

Controls the spacing between nodes in the force simulation. This is purely visual — it doesn't change which documents are connected, just how far apart they're drawn.

- **Low spread (10–50%)** — nodes cluster tightly together. Good for seeing overall structure.
- **Default spread (100%)** — balanced spacing.
- **High spread (150–200%)** — nodes spread far apart. Good for reading labels on individual nodes.

Changing spread reheats the physics simulation so nodes reposition smoothly.

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
