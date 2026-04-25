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

## Version compatibility

A restore refuses to apply a backup produced by a *newer* mdkb version than the one currently running — the schemas may not be readable. Restoring an *older* backup is allowed; forward-only schema migrations run on the next startup.

This is the safety net that pairs with [release-gating and safe upgrades](../explanation/versioning-and-upgrades.md): take a backup before any upgrade, and you have a guaranteed rollback path.

## Atomicity

Restore is atomic. Existing data is moved aside before new data is written; if anything fails mid-restore the old data is moved back into place. The `.restart-required` marker is written only after a successful swap.

## When to back up

- Before upgrading mdkb to a new version
- Before changing your embedding model (the vector store is invalidated and re-indexed)
- Before destructive operations from the Database panel (clear vector DB, etc.)
- On a schedule, if your knowledge base is critical
