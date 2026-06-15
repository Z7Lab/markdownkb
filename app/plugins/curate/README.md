# curate — corpus growth (analyze–match–codify)

`curate` implements the **growth lever** of the analyze–match–codify loop
described in `knowledge-corpus-growth-loop-guide.md`. That guide stays the
*why/when*; this README is the *mechanics*.

## What it does

An analyzer (the agent) holds *both* a source and the practice corpus and
sorts findings into three buckets:

- **A — codified + present** (confirmation),
- **B — codified, applicable, absent** (a study/gap list),
- **C — practiced, not codified** (the growth lever).

`curate` stores **only bucket-C** candidates as **drafts**, never
auto-merged. Two human gates protect the canonical corpus:

1. **per-run** — analysis is cheap and runs freely; *drafting* is an
   explicit action. The agent only calls `curate_submit_draft` when asked.
2. **per-candidate** — a curator opens the Curate tab, reads/edits each
   draft, and graduates or rejects it by hand.

The loop compounds: each graduated draft enlarges the corpus, so the next
run's A grows, B sharpens, and C shrinks.

## Architecture — compose, don't reinvent

curate adds the one thing mdkb lacks — a **draft/review store with a status
lifecycle** (`curate.db`) — and composes everything else:

| Loop stage | Reused piece |
|---|---|
| A/B/C match (substance, not vocabulary) | the **agent**, via `search` / `bucket-search` |
| write generated content into the corpus | the **`promote_to_wiki` write primitive**, gated |
| absence check, never mutate | mirrors **lint**'s flag-only discipline |

`graduate()` is the **gated analog of `promote_to_wiki`** — the same write
primitive (resolve a writable source → build a document → write → log →
version-commit) with the draft store and two gates in front.

The core is **source-agnostic** from day one: every draft carries
`source_type` / `source_ref`, so the agent path covers both code (`search`
vs a repo) and buckets (`bucket-search` vs `search`) with zero per-source
plugin code. An agent-less "promote from bucket" adapter is a documented
**v2** extension point.

## Drafts

A draft carries the guide's required shape; `submit_draft` hard-requires a
title, a non-trivial body, and a `taxonomy_slot`, and returns
`shape_warnings` for anything thin (missing rationale, worked example, or
honest TODOs).

## Graduation gates & prerequisites

Graduation honors mdkb's three write controls:

- the target must be a configured **`writable: true`** source;
- on the MCP path, **`mcp.save_document`** must be on (the
  `curate_graduate` tool is `write: true`);
- `write_api` is **not** required — `graduate()` writes from the backend,
  like `promote_to_wiki`.

**Prerequisite:** the canonical `knowledge_docs` tree must be a registered
**writable + indexed** source — a setup dependency, not provided by curate.
When no writable source exists, graduation surfaces a clear "graduation
unavailable" error rather than a silent no-op.

**Indexing guard:** `graduate()` refuses any destination matching
`settings.global_ignore`. A file under an ignored segment is written but
never indexed — it would silently break the compounding loop.

## Soft dependencies

Per the established `app.state` / `get_*` pattern (`requires:` in
`plugin.yaml` is declarative-only; the loader never enforces it):

- **search** — substance-matching for the A/B/C sort. Analysis degrades
  without it.
- **promote_to_wiki / save_document** — the reused write primitive.
- **buckets** — soft, only for the deferred v2 agent-less path.
- **lint** — optional; curate mirrors its flag-only discipline.

## Buckets — two unrelated senses

1. The guide's **A/B/C buckets** are finding categories in the agent's
   reasoning — no objects, nothing to clean up.
2. **mdkb buckets** are ephemeral scoped collections curate may read
   *from*. **curate never creates or deletes mdkb buckets** — it reads one
   as a read-only source and records only `source_ref=<bucket id>`. Any
   throwaway bucket an agent stages for curation should be created with
   `expires_in` so the buckets plugin's TTL self-cleans it.

## MCP tools

- `curate_submit_draft` (write) — land a bucket-C candidate.
- `curate_list_drafts` — read the curation queue.
- `curate_graduate` (write) — graduate a reviewed draft.
- `curate_reject` (write) — discard a candidate.

There is **no** MCP tool for the A/B/C match — the agent uses the existing
`search` / `bucket-search` tools.
