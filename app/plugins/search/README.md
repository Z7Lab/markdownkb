# Search Plugin

Semantic search with history, AI summaries, query enhancement, and Google-style exact phrase matching.

**Feature flag:** `search`
**Prefix:** `/api`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/search` | Semantic search with optional query enhancement |
| GET | `/api/v1/searches` | List search history (paginated) |
| GET | `/api/v1/searches/{id}/load` | Load historical search with preserved results |
| GET | `/api/v1/searches/{id}/versions` | Get all versions of a search (original + re-queries) |
| GET | `/api/v1/searches/{id}/compare` | Compare historical search against current KB state |
| DELETE | `/api/v1/searches/{id}` | Delete a search from history |
| POST | `/api/v1/search/summarize` | AI summary of search results (streaming SSE). Pass `deep_research: true` for MCTS multi-angle synthesis. |
| POST | `/api/v1/search/enhance-query` | LLM query enhancement (keyword extraction, acronym expansion) |

## Exact Phrase Matching

Wrap terms in double quotes for exact matching: `"kubernetes deployment"` requires the literal phrase in chunk content. Unquoted terms use semantic (vector) search. Multiple quoted phrases are AND-ed.

Implementation: quoted phrases are extracted via regex, quote characters are stripped from the vector query (keeping the words for semantic recall), and chunks are post-filtered for literal matches. A higher chunk multiplier is used when phrases are active to compensate for filtering losses.

## Configuration

Configurable via `plugins.search` in `settings.yaml`:

| Key | Default | Description |
|-----|---------|-------------|
| `chunk_multiplier` | `10` | Chunks fetched per result (higher = more file diversity) |
| `exact_phrase_multiplier` | `20` | Chunk multiplier when quoted phrases are used |
| `exact_phrase_matching` | `true` | Enable/disable quoted phrase exact matching |

```yaml
plugins:
  search:
    chunk_multiplier: 10
    exact_phrase_multiplier: 20
    exact_phrase_matching: true
```

## Deep Research

When `deep_research: true` is passed to the summarize endpoint and the `deep_research` feature flag is enabled, the search plugin delegates to `app/services/deep_research.py` instead of generating a single-pass summary. This runs the MCTS engine to explore multiple research angles before synthesizing a comprehensive answer. The toggle is available in the Search tab UI.

## Dependencies

- `app.rag.retriever` — hybrid vector + BM25 search
- `app.rag.llm` — streaming LLM completions (for summaries)
- `app.storage.searchdb` — search history persistence
- `app.storage.scopedb` — scope resolution
- `app.services.query_service` — intelligent query enhancement
- `app.services.deep_research` — MCTS deep research synthesis (optional, feature-gated)
