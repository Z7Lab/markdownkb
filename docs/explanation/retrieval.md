# How Retrieval Works

How mdkb finds relevant documents when you search, chat, or plan. Understanding the retrieval pipeline helps you tune search quality and understand why results appear the way they do.

## The Two-Strategy Approach

mdkb uses **hybrid search** — combining two different search strategies that complement each other:

### Vector Similarity (Semantic Search)

Your query is converted to a numerical vector (embedding) using the same model that indexed your documents. This vector is compared against every chunk's vector in ChromaDB using cosine similarity.

**What it's good at:** Finding conceptually related content even when the words don't match. A query for "how do we handle authentication" finds chunks about "API key middleware", "session tokens", and "security patterns" — because the meaning is similar even though the keywords differ.

**What it misses:** Exact terms, proper nouns, specific identifiers. A query for "MCTS planner" might miss a chunk that literally says "MCTS planner" but has a low overall semantic similarity score because the surrounding text is about something else.

### BM25 Keyword Matching

BM25 (Best Matching 25) is a classic information retrieval algorithm that scores documents by term frequency — how often your query words appear in each chunk, weighted by how rare those words are across all documents.

**What it's good at:** Finding exact keyword matches, proper nouns, technical terms, acronyms. A query for "MCTS" finds every chunk that contains "MCTS" regardless of surrounding context.

**What it misses:** Synonyms and conceptual similarity. A query for "planning algorithm" won't find chunks that say "MCTS" unless they also contain the word "planning."

### Why Both

Neither strategy alone is sufficient:

- Vector-only search misses exact term matches buried in semantically dissimilar content
- Keyword-only search misses conceptually related content that uses different terminology
- Hybrid combines both: the BM25 score catches keyword matches the vector search missed, and the vector score catches semantic matches the keywords missed

The final score is a weighted combination:

```
hybrid_score = (1 - bm25_weight) * vector_score + bm25_weight * bm25_score
```

## Score Fusion

After both search strategies produce scores for each chunk, they're fused into a single ranking:

1. **Vector search** returns the top `N` chunks ranked by cosine similarity (0 to 1, where 1 is identical)
2. **BM25 search** scores the same chunks by keyword relevance
3. BM25 scores are normalized to the 0–1 range
4. Scores are combined using the weighted formula above
5. Results below the `score_threshold` are filtered out
6. The top `top_k` results are returned

## Post-Retrieval Filtering

After scoring, results pass through several filters in order:

1. **Scope folder filter** — if a scope with folders is active, only chunks from those folders pass
2. **Scope tag filter** — if scope tags or ad-hoc tags are active, only chunks from matching documents pass
3. **Exclude patterns** — if the active scope has exclude patterns, chunks from matching files are removed
4. **RAG exclusion** — files toggled off in the Files tab are removed
5. **File deduplication** — for search results (not chat), chunks are grouped by source file and the best-scoring chunk per file determines the file's ranking

## Chunk Overlap

When documents are split into chunks during indexing (see [Chunking](chunking.md)), consecutive chunks share an overlap region — the last N characters of one chunk are repeated at the start of the next. This serves two purposes:

1. **Context continuity** — a sentence split across a chunk boundary appears in both chunks, so it can be found by either
2. **Retrieval redundancy** — if the relevant passage spans a boundary, at least one chunk contains enough of it to match the query

The default overlap is 150 characters (~37 tokens). Higher overlap means more retrieval redundancy at the cost of slightly more storage and embedding computation.

## Configuration

All retrieval settings are in `config/settings.yaml` under `retrieval:`:

```yaml
retrieval:
  top_k: 10              # max results returned
  score_threshold: 0.25  # minimum score to include (0.0–1.0)
  hybrid_search: true    # enable BM25 + vector fusion
  bm25_weight: 0.5       # keyword vs semantic balance (0.0 = vector only, 1.0 = BM25 only)
```

| Setting | Default | Effect |
|---------|---------|--------|
| `top_k` | 10 | How many chunks/results to return. Higher = more context for the LLM but slower and more expensive. |
| `score_threshold` | 0.25 | Minimum hybrid score. Lower = more results but potentially less relevant. Higher = fewer but more precise results. |
| `hybrid_search` | true | When false, only vector similarity is used (no BM25 component). |
| `bm25_weight` | 0.5 | Balance between keyword and semantic matching. 0.5 = equal weight. Increase for keyword-heavy queries, decrease for concept-heavy queries. |

These can also be saved as **retrieval presets** in Settings for quick switching between different tuning profiles.

## Tuning Tips

**Getting too many irrelevant results?** Raise `score_threshold` from 0.25 to 0.35 or higher.

**Missing results you know exist?** Lower `score_threshold`. Also check that hybrid search is enabled — pure vector search can miss exact keyword matches.

**Technical queries (code, identifiers, acronyms)?** Increase `bm25_weight` toward 0.6–0.7 to favor keyword matching.

**Conceptual queries (explanations, patterns, decisions)?** Decrease `bm25_weight` toward 0.3–0.4 to favor semantic matching.

**Scope filtering returns nothing?** Make sure the documents you're looking for are actually in the selected scope's folders or have the right tags. Check Settings > Scopes to verify.

## How It Connects to the Rest

- **Chat** retrieves chunks, builds a prompt with the context, and streams the LLM response. The `top_k` setting controls how much context the LLM sees.
- **Search** retrieves chunks, groups them by file, and displays ranked results. The search plugin multiplies `top_k` by a `chunk_multiplier` (default 10) to fetch more chunks before deduplication.
- **Planner** retrieves chunks as research context for the MCTS planning algorithm.
- **Doc Map** doesn't use the retriever — it works directly with embeddings from ChromaDB to compute document-level similarity.

## Implementation

| File | Purpose |
|------|---------|
| `app/rag/retriever.py` | Hybrid search, BM25, score fusion, post-filtering |
| `app/storage/vectorstore.py` | ChromaDB wrapper — query, add, delete |
| `app/ingestion/parser.py` | Chunking (see [Chunking](chunking.md)) |
| `app/config/__init__.py` | Retrieval settings properties |
