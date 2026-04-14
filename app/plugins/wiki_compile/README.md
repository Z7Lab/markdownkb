# Wiki Compile Plugin

Karpathy-style wiki compilation — read a source document, synthesize a summary page into a managed wiki, and maintain `index.md` and `log.md` for navigation.

**Feature flag:** `wiki_compile`
**Prefix:** `/api/wiki-compile`

## The pattern

Implements the *Ingest* verb of the three-verb wiki pattern described in [Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). The full pattern has three operations: **Ingest** (this plugin), **Query** (already covered by mdkb's hybrid search), and **Lint** (a separate follow-up plugin).

The compilation layer respects mdkb's three-tier knowledge model:

- **Raw sources** — immutable. Read but never modified.
- **Derived (this plugin's target)** — LLM-generated pages written into a managed wiki.
- **Canonical** — human-authored docs under non-writable sources. Never touched by this plugin.

A *wiki* is a named, persistent target with a managed path. Create one by name; the plugin handles directory creation, registration as a writable source, and (in Docker) the bind-mount via `compose.override.yml`. Ingest calls reference a wiki by name.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/wiki-compile/wikis` | List managed wikis |
| POST | `/api/wiki-compile/wikis` | Create a managed wiki |
| DELETE | `/api/wiki-compile/wikis/{name}` | Deregister a wiki (directory preserved on disk) |
| POST | `/api/wiki-compile/ingest` | Ingest a source into a wiki by name |

## POST /wikis request body

```json
{
  "name": "research",
  "path": "/optional/custom/path"
}
```

- `name` — unique wiki name. Used by `/ingest`'s `wiki` argument.
- `path` (optional) — override the default location. Default is `{data_directory}/wikis/{name}/`, which is inside the existing data-dir mount, so no Docker restart is needed. A custom path outside the project/data dir gets added to `compose.override.yml` and the response flags `docker_restart_required: true`.

## POST /ingest request body

```json
{
  "source_path": "/absolute/path/to/source.md",
  "wiki": "research",
  "force": false
}
```

- `source_path` — any readable file on disk. Does not need to be a configured source. Content is truncated to 8000 characters before the LLM call.
- `wiki` — managed wiki name. Resolved via WikiDB to a path.
- `force` — if `true`, overwrites an existing summary page for the same source. Default `false`.

## What it writes

For a source with slug `karpathy-llm-wiki-gist` ingested into the `research` wiki:

```
{wiki_path}/
├── summaries/
│   └── karpathy-llm-wiki-gist.md     # LLM-generated summary page
├── index.md                           # regenerated every ingest
└── log.md                             # appended every ingest
```

- **`summaries/<slug>.md`** — the LLM output: `# Title` heading, 2–4 paragraphs synthesizing the source, `## Source` section citing the path. The prompt explicitly forbids opinions, inline academic citations, and wiki-style `[[double-bracket]]` links.
- **`index.md`** — a catalog grouped by top-level subdirectory, with each page linked by its H1 title. Rebuilt from scratch every ingest.
- **`log.md`** — appended with `## [YYYY-MM-DD] ingest | <filename>` per the gist's convention. Parseable via `grep '^## \[' log.md`.

## LLM

Uses `app.rag.llm.get_completion` — the same single-provider-with-fallback path as search summarize and edge explain. Runs against whichever provider is configured as active (Ollama, Venice, Anthropic, etc.). Works with local models by default — this plugin makes no assumption that a frontier model is available. The compilation pattern works with any model capable of producing coherent markdown.

## Retrieval-augmented context

Before each LLM call, the plugin fetches the most-related existing wiki pages from the target directory and passes them to the LLM as context. The system prompt instructs the model to note where the new source agrees with, extends, or contradicts those existing pages — in the new summary only. Existing pages are never modified or proposed for edit; this is a *mention-only* behavior.

How it works:

- The first ~1500 chars of the new source are used as the embedding query. Not a budget cap — using the full source as a query dilutes the signal and duplicates material that already appears below in the prompt.
- The hybrid retriever (vector + BM25) is scoped to the target directory via `folders_filter`, so only this wiki's pages are candidates.
- Returned chunks are deduped to unique source pages; `index.md` and `log.md` are excluded.
- Each surviving page's full content is embedded in the user prompt under an `### Existing: <filename>` heading.
- When the wiki is empty, the retriever is offline, or no related pages are found, the context block is an empty string and the LLM call falls back to a plain summary.

The context shape is driven entirely by the retriever's configuration. Its `top_k` and score thresholds decide how many pages survive — this plugin adds no additional token-budget caps. A small-context deployment with a low `top_k` naturally gets fewer pages; a large-context one with a higher `top_k` gets more. One knob, the right scope.

## Idempotency

Re-ingesting a source whose summary already exists returns 400 with a message pointing at `force=true`. The log is append-only (duplicate ingests appear as separate entries, letting a reader see the history of overwrites).

## What's out of scope

- **Editing existing pages.** This plugin reads existing pages as context and lets the LLM mention overlaps in the *new* summary, but never modifies the existing pages themselves. A future version would let the LLM propose structured edits to existing pages — that's a different response shape and is tracked separately.
- **Lint passes.** Contradiction detection, stale-claim flagging, orphan detection, cross-tier comparisons. All belong to a sibling plugin queued separately.
- **Promoting chat/search output to pages.** Different UX — driven from the chat/search tab, not from a source file. Queued separately as the "promote to wiki" feature.
- **Schema files.** A per-wiki schema file (YAML or markdown-with-frontmatter) to configure page conventions was described in the original spec but deferred. The current version uses sensible defaults hard-coded in `prompts.py`.

## Caching and invalidation

No caching — every ingest runs a fresh LLM call. Adding an in-memory cache keyed by `(source_path, source_content_hash)` is a straightforward extension if call cost becomes painful. Edge-explain uses that pattern already.
