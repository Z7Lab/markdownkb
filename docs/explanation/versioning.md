# Versioning

MarkdownKB keeps a git-backed revision history of every document it writes. Each write through the [Write API](../how-to/writing-documents.md) or the [wiki_compile](wiki-compile.md) plugin is automatically committed to a per-source managed git repo. Users can browse history, view diffs, and restore past revisions from the file viewer.

## Why versioning lives inside MarkdownKB

The [markdown-first paradigm](manifesto.md) treats captured intelligence as an asset that compounds over time. That compounding only works if the base stays trustworthy: a bad AI generation, a mis-scoped overwrite, or a stale document that turned out to matter six months later shouldn't quietly erase what came before.

External git is the classic answer, but it has real friction in this context:

- **Not every source belongs in a user-facing repo.** A wiki at `{data_dir}/wikis/research/` isn't something the user would initialize as their own git repo — it's mdkb-managed infrastructure.
- **Mixing mdkb's commits with the user's own is messy.** If a source is already a git repo the user commits to (e.g. a project's `/docs` folder), every `save_file` call would show up in their working tree and clutter their own history.
- **Restoring requires ceremony.** Finding the right commit, checking out an old blob, writing it back — none of it is built into the tool the user already has open.

Building versioning into MarkdownKB sidesteps all of this. The history is always there, invisible when you don't need it, one click away when you do. And because it's git under the hood, it's not a proprietary format — you can export the repo and treat it like any other git history.

## The trust boundary, revisited

The [philosophy doc](manifesto.md#the-trust-boundary) names compounding errors as the main failure mode of the capture loop: an AI-generated doc that was confidently wrong enters the base, future agents retrieve it, the error propagates. Versioning doesn't stop that from happening — human review is still the quality gate — but it does make the gate recoverable. You can roll back an overwrite. You can diff what changed between two revisions to spot where a model drifted. You can trace when a doc stopped being accurate.

In the compounding-knowledge loop, versioning is the safety net mentioned under *version history is your safety net.* It turns every accidental write into a fixable mistake instead of a lost file.

## What gets versioned

A source is versioned when its configuration has `versioned: true`. The default is to mirror `writable` — writable sources are versioned unless you opt out. Read-only sources are never versioned (there's nothing to commit; mdkb can't write to them).

| Source kind | `writable` default | `versioned` default | Rationale |
|-------------|--------------------|--------------------|-----------|
| Raw tier-1 docs (your project, your research) | `false` | `false` | You version these yourself, in your own git |
| Derived tier-1 docs (wikis, scratch captures) | `true` | `true` | mdkb owns the writes, so mdkb owns the history |
| Canonical tier-0 docs (reviewed, promoted) | usually `false` | `false` | Protected; human review is the control |

Three types of writes trigger auto-commits today:

- **Write API** — every `POST /api/v1/documents` and `DELETE /api/v1/documents` commits the written (or removed) file.
- **MCP `save_file` / `delete_file`** — same path, different interface. Agents that write through MCP get the same version trail.
- **wiki_compile ingest** — each ingest produces one commit covering the summary, `index.md`, and `log.md` with a message like `wiki_compile: ingest <source-filename>`.

Writes that happen outside mdkb — a user editing the file in their own editor, or a script writing directly to disk — are not auto-committed. The file watcher picks them up and reindexes, but the version repo only records mdkb-authored writes. That's deliberate: mdkb doesn't want to race the user's own git workflow.

## How the managed repos are laid out

For every versioned source, MarkdownKB maintains one git repository under `{data_dir}/versioning/<source-hash>/`, where `<source-hash>` is the first 16 hex characters of `sha256(resolved_source_path)`. The `.git` directory lives inside that managed directory; `--git-dir` + `--work-tree` flags bind it to the real source path on the fly.

The upshot: **no `.git` folder appears inside the source itself.** The user's own git repo at the source path (if any) stays untouched. If the user later wants to collapse mdkb's history into their own repo, the managed gitdir can be copied out — commits are authored as `mdkb <mdkb@localhost>` so they remain distinguishable.

A marker file `MDKB_MANAGED` inside each managed repo dir identifies it as mdkb-owned for operators debugging the data directory.

## Three surfaces

**File viewer.** Open any markdown file, click **History**. You get a list of commits with dates and subjects (newest first, tagged `current`), a unified diff view for the selected commit, and a **Restore this version** button for older revisions. Restoring writes the old contents back as a new commit — never a history rewrite. See [Write History in writing-documents.md](../how-to/writing-documents.md#version-history) for the workflow.

**HTTP API.** [`/api/v1/versioning/history|diff|content`](../reference/api.md#versioning) and `POST /api/v1/versioning/restore`. Returns JSON; used by the UI and by any tool that wants to integrate. Writes return a `version_commit` field so a caller can reference the new commit without re-querying history.

**Configuration.** [`core.versioning`](../reference/configuration.md#versioning) as a global kill-switch (toggled from the Plugins settings tab alongside `file_watcher`, `deep_research`, etc.), and per-source `versioned: true|false`. The repos live at `versioning.root`, which defaults to `{data_dir}/versioning/` but can be relocated.

## Deliberate non-goals for v0.1

These are out of scope on purpose:

- **Branching, merging, conflicts.** mdkb is the only writer to each managed repo. No branches, no rebases. If the user wants branching they can export the repo and work with it externally.
- **Integrating with an existing user git repo at the source path.** Too invasive — mdkb would be writing into a workspace the user owns. Kept as a separate concern.
- **Indexer-triggered commits.** Indexing is a read-side operation. It doesn't change file contents and so has nothing to commit.
- **Signed commits.** Not needed for local provenance; re-add if a deployment requires it.
- **Squash/debounce for wiki_compile.** Today each ingest is already one commit (not one per page). Future write paths that produce many small writes in sequence may need debouncing — that's a change to the hook, not the manager.

## When versioning is the wrong answer

A source you version in your own git, with your own conventions, probably shouldn't be re-versioned by mdkb. Set `versioned: false` on those sources. The rule of thumb: if you'd be upset to find mdkb quietly committing to this directory behind your back, turn versioning off for it. The default of "version writable sources" is correct for sources mdkb actually owns — wikis, agent outputs, scratch captures — and wrong for sources you've let mdkb write into as a convenience.

## Related

- [Versioning and Upgrades](versioning-and-upgrades.md) — app version management, update detection, and schema migrations (a different versioning system from the one described here)
- [Writing Documents](../how-to/writing-documents.md) — how the Write API and MCP tools trigger commits
- [Wiki Compile](wiki-compile.md) — the plugin that produces the densest write traffic, and what one ingest's commit contains
- [Configuration: Versioning](../reference/configuration.md#versioning) — the full config surface
- [API: Versioning](../reference/api.md#versioning) — the endpoint reference
- [Philosophy: The Trust Boundary](manifesto.md#the-trust-boundary) — why the safety net matters
