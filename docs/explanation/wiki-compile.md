# Wiki Compile

Wiki Compile turns dense, unstructured source material into structured summary pages that the rest of MarkdownKB can search, retrieve, and reason over. It's the concrete implementation of the "capture intelligence output as queryable markdown" principle from [philosophy.md](philosophy.md) — but for material you *didn't* produce interactively with an LLM. Point it at a paper, a transcript, a vendor's whitepaper, a meeting note, and it writes a synthesized summary page into a writable source directory.

## Where this comes from

The pattern is Andrej Karpathy's ["LLM Wiki" gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), which describes three operations over a personal knowledge wiki: **Ingest** (add new sources and have the LLM integrate them into the wiki), **Query** (ask questions against the wiki), and **Lint** (periodically health-check for contradictions, stale claims, orphan pages, missing cross-references).

MarkdownKB already does Query well — that's what the chat, search, and doc map surfaces are for. The `wiki_compile` plugin implements Ingest. A separate (future) plugin implements Lint. The three verbs are architecturally independent: you can run all three, or use MarkdownKB purely as a retrieval substrate and do ingestion by hand.

The compile step is what most RAG systems skip. Naive RAG retrieves from raw documents at query time, so the LLM rediscovers the connections between sources on every question. A compiled wiki pre-synthesizes those connections once, offline, and the query-time retrieval pulls from compiled pages instead of raw material. Same retrieval pipeline; better retrieved content.

## The three-tier model

Wiki Compile respects a three-tier knowledge model:

- **Raw sources** (Tier -1). Immutable. The plugin reads from them but never writes. Papers, transcripts, captures from the browser, dumps from other systems. Live under any MarkdownKB source — writable or read-only.
- **Derived pages** (Tier 1). LLM-synthesized. The plugin owns this layer. Always lands in a source configured with `writable: true`. This is the compiled wiki — summary pages, the index, the log.
- **Canonical pages** (Tier 0). Human-authored. Project identity docs, design commitments, architectural positions. Live under sources configured with `writable: false`. The plugin *cannot* reach them — the writable-source requirement is enforced at the endpoint layer. An LLM can suggest changes to canonical docs (via queued tasks, diffs, review requests) but can never apply them.

This separation matters because a personal reading wiki can safely let an LLM rewrite everything. A project whose identity *is* its positioning cannot. The write-protection on canonical docs is what keeps the human in charge of who the project is, even while the LLM builds out what the project knows.

## What a compile pass does

For a single source file ingested into a writable target:

1. **Read** the raw source from disk (truncated to ~8000 characters to keep prompt cost bounded).
2. **Synthesize** a summary page via the configured LLM — the same provider used for search summaries and edge explanations. The prompt asks for a `# Title` heading, 2–4 paragraphs naming specific entities/decisions/numbers (not generic descriptions), and a `## Source` section citing the path verbatim. The prompt explicitly forbids opinions, inline academic citations, and wiki-style double-bracket links.
3. **Write** the page to `<target>/summaries/<slug>.md`.
4. **Rebuild** `<target>/index.md` from scratch — a catalog grouped by top-level subdirectory, each page linked by its H1 title.
5. **Append** to `<target>/log.md` with a dated entry: `## [YYYY-MM-DD] ingest | <filename>`. The log is append-only so the history of changes is preserved even when pages get overwritten.

The compiled pages are ordinary markdown in an ordinary source directory. Everything downstream picks them up automatically: the indexer re-embeds them on the next watch cycle, hybrid search surfaces them alongside raw documents, the doc map plots them with the rest of the graph, chat retrieves from them, MCP clients see them. No special integration is required because the compiled output doesn't look special.

## Why this matters for the compounding loop

The philosophy doc argues that every AI interaction produces token output, and the default behavior is to let it evaporate. `wiki_compile` extends that argument to inputs the LLM didn't produce but did read. When you drop a paper into a bucket, search it once for what you needed, and move on, the LLM's understanding of that paper is gone. When you compile the paper instead, the understanding persists as a markdown page that:

- Is searchable by keyword and semantics
- Cites its source explicitly
- Gets clustered in the doc map with other material on the same topic
- Can be referenced by chat answers and planner outputs
- Can be promoted into canonical docs by a human on a deliberate editing pass

The next time a question comes up about that topic, the compiled page is in the retrieval corpus — so the answer is grounded not just in what the paper said but in what you've already distilled from it. That's the loop.

## When to use it

**Use it for** dense material you want to query later: research papers, conference talks, long blog posts, vendor whitepapers, meeting transcripts, research notes, reading notes. Material where the original is useful to keep around but not how you want to think about it.

**Don't use it for** material that's already structured and concise: your own project docs (you already wrote them well), code files (grep and file navigation beat RAG), reference lists (no synthesis needed). The compile step adds latency and LLM cost, so skip it when the source is already the right shape.

## Limitations (v1)

- **One verb, one page.** `wiki_compile` v1 writes a summary page per source. It does not yet update existing entity or concept pages when new sources are ingested. A richer version — which reads the existing wiki and proposes cross-references or revisions — is a follow-up.
- **No schema file.** Karpathy's gist describes a schema file (CLAUDE.md or AGENTS.md) that tells the LLM the wiki's conventions, page templates, and workflows. v1 uses hard-coded defaults. A per-target schema is a natural v2 addition.
- **No in-UI ingest.** Compilation is CLI/API-only right now. A future "ingest this bucket doc" button is a planned UI gesture.
- **No lint.** The Lint verb belongs to a separate plugin (queued, not built). Without it, the compiled wiki can drift — contradictions between pages, stale claims, orphan pages — and there's no automated detection.
- **No automatic re-compilation on source change.** If the raw source file changes, the compiled page stays stale until you re-ingest with `force=true`. Detecting source drift and flagging it for re-compile is a straightforward extension.

## Plugin reference

Feature flag: `wiki_compile`. API prefix: `/api/wiki-compile`. Full endpoint docs: [api.md](../reference/api.md#wiki-compile). Plugin source and README: `app/plugins/wiki_compile/`.
