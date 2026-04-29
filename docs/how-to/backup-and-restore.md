# Backup and Restore

MarkdownKB can export its full state as a single portable archive — databases, vector embeddings, plugin data, and (optionally) configuration — and restore that archive on the same machine or a different one.

## What's in a backup

| Always included            | Optional (on by default)  | Optional (off by default) | Never included         |
| -------------------------- | ------------------------- | ------------------------- | ---------------------- |
| All SQLite databases       | ChromaDB vector store     | `config/settings.yaml`    | API keys / secrets     |
| Plans (`plans/`)           |                           | `compose.override.yml`    | Embedding model weights |
| Plugin data (`plugins/`)   |                           | Source files              | Versioning git repos   |
|                            |                           |                           | Log files              |

The vector store (ChromaDB) is the largest part of a backup — typically hundreds of MB for a large knowledge base. Uncheck **Include vector embeddings** to produce a much smaller archive that still preserves all your chats, searches, plans, scopes, buckets, and tags. You will need to re-index after restoring to rebuild the vectors.

Databases are snapshotted with SQLite's online backup API, so the archive is consistent even while the app is running.

## Create a backup

In the UI: **Settings → Backup & Restore → Create Backup**. Choose whether to include configuration and source files, then click **Download Backup**. Your browser saves a single `mdkb-backup-<timestamp>.tar.gz`.

Behind the scenes:

```
POST /api/v1/backups/create
{ "include_config": true, "include_chromadb": true, "include_sources": false }
```

The response streams the archive directly to the client.

## Restore a backup

In the UI: **Settings → Backup & Restore → Choose Backup File**. The manifest is shown for confirmation (creation date, source mdkb version, contents). Click **Restore** to apply.

After a successful restore, MarkdownKB writes a `.restart-required` marker in the data directory and the UI shows a banner asking you to restart the container:

```
make docker-restart
```

Once restarted, click **I've restarted — clear this notice** to dismiss the banner.

## What replaces what

A restore replaces all SQLite databases, the ChromaDB vector store, and the `plans/` and `plugins/` directories. Secrets and embedding model weights in the data directory are never touched.

If the backup was created with **Include configuration** enabled, you can opt to apply the included `settings.yaml` and `compose.override.yml`. Skip this if you're restoring onto a machine with different paths or a different LLM setup.

If the backup was created with **Include source files** enabled, the source directories are unpacked into `data/restored-sources/`. You move them into place manually — your watch-dir paths on the new machine may differ from the original.

## Switching embedding models

Changing your embedding model wipes the entire vector store. Embeddings are high-dimensional floating-point vectors — `bge-small-en-v1.5` produces 384-dimensional vectors, `nomic-embed-text-v1.5` produces 768-dimensional ones. The two shapes are fundamentally incompatible: you cannot compare a 384-dim vector to a 768-dim vector, and ChromaDB enforces a single fixed dimension per collection. Switching models means all existing embeddings are invalid and must be discarded.

**What is preserved across a model switch:**

| Preserved | Lost |
| --------- | ---- |
| All chat conversations | ChromaDB vector embeddings |
| Search history | Indexed chunk text (re-extracted on re-index) |
| Plans | |
| Scopes and presets | |
| Tags | |
| Buckets and their metadata | Bucket vector embeddings (same issue) |
| Versioning history | |

**Recommended flow before switching:**

1. **Settings → Backup & Restore → Create Backup** — include the vector store if you want to be able to roll back to the old model without re-indexing.
2. In Settings → Embedding Model, select and download the new model.
3. In Settings → Database, clear the vector store.
4. Trigger a full re-index.

Buckets each have their own ChromaDB collection. After switching models, re-upload documents to any buckets you want to keep — the metadata (title, creation date, tags) is preserved in SQLite; only the vectors need to be rebuilt.

## Embedding model mismatch (when restoring)

Each backup records which embedding model was active when it was created. If the restored backup used a different model than the one currently configured (e.g. backup was `bge-small-en-v1.5` but you're now on `nomic-embed-text-v1.5`), the restart banner will show a warning explaining the mismatch.

The stored vectors are incompatible — searching will return wrong results and indexing new files will be blocked with a 409 error until you resolve the conflict. You have two options:

- **Re-index**: go to Settings → Database, clear the vector store, then trigger a full re-index with your current model.
- **Switch back**: change your embedding model back to the one the backup was built with, then re-index.

## If indexed files disappear after a Docker restart

After a `make docker-restart` or `make docker-up`, the file list can appear empty — all previously indexed documents gone. **Your source files are safe.** They live on the host filesystem and were never touched. What happened is that MarkdownKB's scanner runs on startup, finds the source paths not mounted inside the container, and prunes those paths from the index (treating them as deleted files).

**Root cause:** source directory mounts live in `compose.override.yml` (project root) and `config/compose.override.yml`. When Docker Compose is invoked with explicit `-f` flags — as the `docker-build-full` and variant targets do — it ignores the `COMPOSE_FILE` env var entirely. If either override file is missing from the `-f` chain, the source mounts are silently absent.

The `make` targets handle this correctly and include both override files. If you ran `docker compose` by hand and omitted the override files, that's the likely cause.

**To recover:**

1. Check that both override files exist and contain your source mounts:
   ```bash
   cat compose.override.yml
   cat config/compose.override.yml
   ```
2. Stop and restart with the full override chain:
   ```bash
   make docker-down && make docker-up
   ```
3. On startup, the scanner will detect the now-mounted paths and re-index them. No re-uploading needed — the files were always there.

If sources are missing from the override files entirely, re-add them via **Settings → Sources** and restart. The UI writes the mount entry automatically.

## Versioning

MarkdownKB tracks the full edit history of every indexed markdown file in a per-file git repository stored in `data/versioning/`. Every write (via the editor, the API, or an MCP write tool) creates a new commit. You can browse history in the file viewer's **History** tab, diff any two versions, and restore a previous version.

Versioning history survives backups, restores, and model switches — it's part of the SQLite + filesystem state that is always preserved. It is _not_ included in the backup archive by default (versioning git repos are listed under "Never included"), because they can be large and are rarely needed on a new machine.

See [Versioning](../explanation/versioning.md) for the full reference — history API, export, and configuration.

## Exporting your markdown files

Two dedicated export actions are available under **Settings → Backup & Restore**:

### Markdown Archive

**Download Markdown Archive** produces a `.zip` of every indexed markdown file, organised into three subdirectories:

| Directory | Contents |
| --------- | -------- |
| `sources/` | All files tracked in the index (`status=complete`, included in index), grouped by their source root directory |
| `buckets/` | Each non-expired bucket's documents, reconstructed from ChromaDB chunks — one subdirectory per bucket |
| `wikis/` | All `.md` files from wiki_compile output directories (if the `wiki_compile` plugin is enabled) |

No databases, no embeddings, no config — just the markdown content. This is the fastest way to get all your knowledge into a portable form.

### System Backup with markdown content

The **Create System Backup** card has an **Include markdown content** checkbox. When enabled, the backup gains a `markdown/` subtree identical to the Markdown Archive above, alongside the databases and configuration. The archive is still fully restorable — the `markdown/` directory is supplemental and not applied during restore.

Use this when you want a single portable archive that contains both the system state (for recovery) and all readable content (for archival or migration).



A restore refuses to apply a backup produced by a *newer* mdkb version than the one currently running — the schemas may not be readable. Restoring an *older* backup is allowed; forward-only schema migrations run on the next startup.

This is the safety net that pairs with [release-gating and safe upgrades](../explanation/versioning-and-upgrades.md): take a backup before any upgrade, and you have a guaranteed rollback path.

## Atomicity

Restore is atomic. Existing data is moved aside before new data is written; if anything fails mid-restore the old data is moved back into place. The `.restart-required` marker is written only after a successful swap.

## Routine database maintenance

Over time the vector database can accumulate orphaned data: chunks whose source files were deleted, and HNSW segment directories left behind when buckets or collections are removed. These don't affect correctness but do waste disk space.

**Settings → Database → Vector Database → Maintenance → Scan** inspects the database without modifying anything and reports:

- **Orphaned chunks** — vectors whose source file no longer exists on disk
- **Orphaned segment dirs** — UUID directories in the ChromaDB folder with no matching segment record
- **VACUUM estimate** — SQLite free pages reclaimable by VACUUM

After scanning, action buttons appear for any issues found:

- **Cleanup Orphans** — deletes the orphaned vectors and removes the corresponding tracking rows
- **Compact Vector DB** — deletes orphaned segment directories and runs `VACUUM` on `chroma.sqlite3`

The orphan operations are safe to run while the app is running. VACUUM requires no active database writes; if it fails, the panel shows a recovery hint (`make docker-restart` in Docker, or restart the app in native mode).

## When to back up

- Before upgrading mdkb to a new version
- Before changing your embedding model (the vector store is wiped — see [Switching embedding models](#switching-embedding-models))
- Before destructive operations from the Database panel (clear vector DB, etc.)
- On a schedule, if your knowledge base is critical
