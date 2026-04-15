# Knowledge Graph Plugin

3D document similarity graph visualization with clustering, word clouds, and scope/tag filtering.

**Feature flag:** `graph`
**Prefix:** `/api/v1/graph`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/graph/data` | Compute similarity graph (nodes, edges, clusters, word clouds) |
| GET | `/api/v1/graph/stats` | Lightweight stats (doc count, chunk count) without full computation |
| GET | `/api/v1/graph/status` | Check if cached graph data is available (no computation) |
| GET | `/api/v1/graph/edge-detail` | Chunk-level similarity detail for a document pair |
| GET | `/api/v1/graph/progress` | Current graph computation progress |

## Query Parameters

`/api/v1/graph/data` accepts:
- `scope_id` / `scope_ids` — restrict to a named scope
- `ad_hoc_tags[]` — filter by tags
- `top_k` (default: 3) — edges per node
- `word_clouds` (default: true) — include word cloud data
- `min_weight` (default: 0.5) — minimum edge similarity weight

## Caching

Graph data is cached in-memory keyed by (folders, tags, top_k, word_clouds, min_weight). The cache is automatically invalidated when files are indexed or deleted, via a background thread subscribed to the `IndexEventBus`.

## Dependencies

- `app.rag.retriever` — vector store access
- `app.services.graph_service` — graph computation and edge detail
- `app.events` — event bus for cache invalidation
- `app.storage.scopedb` — scope resolution
