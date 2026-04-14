# Wiki Compile Plugin

Karpathy-style wiki compilation — read a source document, synthesize a summary page into a writable source directory, and maintain `index.md` and `log.md` for navigation.

**Feature flag:** `wiki_compile`
**Prefix:** `/api/wiki-compile`

## The pattern

Implements the *Ingest* verb of the three-verb wiki pattern described in [Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). The full pattern has three operations: **Ingest** (this plugin), **Query** (already covered by mdkb's hybrid search), and **Lint** (a separate follow-up plugin).

The compilation layer respects mdkb's three-tier knowledge model:

- **Raw sources** — immutable. Read but never modified.
- **Derived (this plugin's target)** — LLM-generated pages written to a configured writable source.
- **Canonical** — human-authored docs under non-writable sources. Never touched by this plugin.

Write-protection is enforced by requiring the target to be a configured source with `writable: true`. Canonical docs live under `writable: false` and are unreachable.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/wiki-compile/targets` | List writable sources that are valid ingest targets |
| POST | `/api/wiki-compile/ingest` | Ingest one source file into a wiki target directory |

## POST /ingest request body

```json
{
  "source_path": "/absolute/path/to/source.md",
  "target_source": "/absolute/path/to/writable/source",
  "force": false
}
```

- `source_path` — any readable file on disk. Does not need to be a configured source. Content is truncated to 8000 characters before the LLM call.
- `target_source` — must match one of the paths returned by `/targets`. Paths that are not configured `writable: true` sources are rejected with a 400.
- `force` — if `true`, overwrites an existing summary page for the same source. Default `false`.

## What it writes

For a source with slug `karpathy-llm-wiki-gist` ingested into target `/path/to/wiki/`:

```
/path/to/wiki/
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

## Idempotency

Re-ingesting a source whose summary already exists returns 400 with a message pointing at `force=true`. The log is append-only (duplicate ingests appear as separate entries, letting a reader see the history of overwrites).

## What's out of scope

- **Updating existing entity/concept pages.** v1 writes only a summary page per source. A richer version would read existing wiki pages and propose cross-references or updates. Tracked separately.
- **Lint passes.** Contradiction detection, stale-claim flagging, orphan detection, cross-tier comparisons. All belong to a sibling plugin queued separately.
- **Promoting chat/search output to pages.** Different UX — driven from the chat/search tab, not from a source file. Queued separately as the "promote to wiki" feature.
- **Schema files.** A per-target schema file (YAML or markdown-with-frontmatter) to configure page conventions was described in the original spec but deferred to v2. v1 uses sensible defaults hard-coded in `prompts.py`.
- **Backlinks, graph overlays, Marp/Dataview integrations.** All Obsidian-side concerns; the compiled wiki is just markdown and plays fine with those tools if the user has them installed.

## Caching and invalidation

No caching in v1 — every ingest runs a fresh LLM call. Adding an in-memory cache keyed by `(source_path, source_content_hash)` is a straightforward extension if call cost becomes painful. Edge-explain uses that pattern already.
