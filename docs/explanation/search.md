# Search & AI Summaries

The Search tab is where you query your knowledge base and get results ranked by relevance, optionally with an AI-generated summary that synthesizes findings across multiple documents. For complex questions, deep research mode runs a multi-angle exploration before summarizing.

Requires the `search` plugin (enabled by default).

## How Search Works

When you enter a query:

1. **Retrieval** — your query is matched against all indexed chunks using [hybrid search](retrieval.md) (vector similarity + BM25 keywords)
2. **Deduplication** — chunks are grouped by source file; each file's score is the best chunk score
3. **Ranking** — files are ranked by their best chunk score
4. **Display** — results show the source file, score, tags, and the most relevant chunk as a preview

The search plugin fetches more chunks than the final result count (controlled by `chunk_multiplier`, default 10×) to ensure file diversity — if a document has many good chunks, it still appears as one result with its best score.

### Exact Phrase Matching

Wrap a term in quotes to require an exact match:

```
"session resume" architecture
```

This finds documents that contain the literal phrase "session resume" AND are semantically related to "architecture." Quoted phrases are matched against the full chunk text (case-insensitive) after retrieval. The search fetches extra chunks (controlled by `exact_phrase_multiplier`, default 20×) to compensate for the stricter filtering.

## AI Summaries

After search results load, you can generate an AI summary that reads the top results and produces a synthesized answer. The summary:

- Reads the highest-scoring chunks across all result documents
- Generates a structured response that draws from multiple sources
- Cites specific documents so you can verify claims
- Streams in real-time as the LLM generates

Summaries are saved alongside the search — when you reload a historical search, its summary is restored too.

**Requires:** An LLM provider configured in Settings > Chat Model.

### Regenerating Summaries

You can regenerate a summary at any time. This is useful after re-querying (new results may change what the summary should say) or if you want a fresh perspective.

## Deep Research Mode

For complex questions that need more than a single retrieval pass, deep research uses **MCTS (Monte Carlo Tree Search)** to explore your query from multiple angles before synthesizing.

Toggle deep research with the "Deep" switch next to the search button.

### How It Works

1. **Research** — retrieves initial context from the knowledge base
2. **Generate approaches** — the LLM proposes N different angles to explore the question (default 3)
3. **Iterate** — MCTS selects the most promising angle (UCB1 algorithm), expands it with additional retrieval, scores it, and repeats for M iterations (default 3, configurable up to 20)
4. **Synthesize** — follows the highest-scoring path through the search tree and generates a comprehensive summary grounded in what was found

Deep research takes longer (30 seconds to several minutes depending on iterations and model speed) but produces more thorough answers for questions that span multiple topics or require connecting information across many documents.

### When to Use It

- **Use regular search** for specific lookups: "what is our rate limiting config?", "how does the file watcher work?"
- **Use deep research** for synthesis questions: "what are all the ways we handle authentication across the system?", "compare our chunking approach to what the research docs recommend"

### Configuration

Deep research requires `core.deep_research: true` in settings.yaml. The iteration count is adjustable per-search (1–20) via the UI control next to the toggle.

## Search History

Every search is saved automatically. The sidebar shows your search history with:

- Query text (used as the title)
- Timestamp
- Icon indicating whether it was a manual search or agent-initiated

### Versioning and Re-querying

When you re-run a search (the "Re-query" button on historical searches), a new **version** is created under the same search entry rather than creating a duplicate. This lets you:

- See how results change over time as your knowledge base grows
- Compare stored results against current results (the "Results changed" indicator)
- Browse all versions of a search via the History button

### Result Change Detection

When viewing a historical search, mdkb compares the stored results against what the same query would return now. If documents have been added, removed, or re-scored, you see a "Results changed" badge with a breakdown:

- **Missing files** — documents in the stored results that are no longer indexed
- **New files** — documents that now match but weren't in the original results
- **Score changes** — documents whose relevance score shifted significantly

This helps you decide whether to re-query for fresher results.

## Query Enhancement

When `retrieval.intelligent_search.enabled` is true, the search query is enhanced by the LLM before retrieval:

- **Keyword extraction** — pulls key terms from natural language queries
- **Acronym expansion** — expands abbreviations (e.g. "KG" → "knowledge graph")

This runs automatically and is transparent — you see the original query, but retrieval uses the enhanced version.

## Search Plugin Configuration

```yaml
plugins:
  search:
    enabled: true
    chunk_multiplier: 10           # chunks fetched per result (higher = more file diversity)
    exact_phrase_multiplier: 20    # chunk multiplier when quoted phrases are used
    exact_phrase_matching: true    # enable/disable quoted phrase exact matching
```

## How It Differs from Chat

- **Search** finds and ranks documents. The AI summary is optional and operates on the results.
- **Chat** retrieves context, then has a conversation. The LLM sees the retrieved chunks as context for answering your question, and you can follow up.

Use search when you want to see what documents exist on a topic. Use chat when you want to ask questions and have a back-and-forth conversation grounded in your knowledge base.
