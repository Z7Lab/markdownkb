# Buckets

Buckets are temporary, isolated document collections with their own vector storage. They let you bring in external documents for focused analysis without mixing them into your permanent knowledge base.

Requires the `buckets` plugin (disabled by default — enable in Settings > Plugins).

## Why Buckets?

Your permanent knowledge base is curated — documents you've decided are worth keeping, organized into source directories, scoped and tagged. But sometimes you need to work with documents temporarily:

- Evaluate a framework by loading its docs and chatting with them
- Investigate an incident by pulling in logs and runbooks
- Compare vendor API docs against your existing architecture
- Load conference notes or tutorial transcripts for a focused session

Buckets keep this temporary content isolated. When you're done, delete the bucket and it's gone — your permanent knowledge base is unchanged.

## Built-in Documentation Bucket

On first startup, MarkdownKB creates a permanent **"MarkdownKB Documentation"** bucket containing its own documentation. You can chat with it to learn the system:

- *"How do I set up a scope with exclude patterns?"*
- *"What's the difference between the doc map and knowledge graph?"*
- *"How does hybrid search work?"*

This bucket has no expiration — it persists until you delete it. If you delete it and want it back, restart the app and it will be recreated.

## How Buckets Work

When you create a bucket:

1. **Source scanning** — markdown files are collected from the paths you specify
2. **Parsing and chunking** — files are split into chunks using the same [chunking pipeline](chunking.md) as the main index
3. **Embedding** — chunks are embedded using the same embedding model
4. **Isolated storage** — embeddings go into a bucket-specific ChromaDB collection, completely separate from the main collection

When you search or chat with a bucket selected, retrieval is scoped to that bucket's collection. Your permanent knowledge base is not searched, and the bucket's content doesn't appear in unscoped searches.

Files assigned to a bucket are excluded from the **Files tab** — they appear in the Buckets tab instead, keeping the two views from overlapping.

## The Buckets Tab

The **Buckets tab** is the primary UI for managing buckets. It has a left sidebar listing all buckets and a main panel for detail and creation.

**Sidebar:** Lists all buckets with a color indicator and file count. Expired buckets are dimmed and badged. Clicking a bucket opens its detail view. The **New Bucket** button at the top of the sidebar opens the creation form.

**Detail panel:** Shows the selected bucket's name, stats (file count, chunk count, created time, expiration), sources, and a file table. Action icons in the header:
- **Edit** (pencil) — opens an inline form to change the name, description, expiration, and color
- **Reindex** (refresh) — re-scans the original sources and indexes any new files
- **Export** (download) — downloads the bucket as a portable zip archive
- **Promote** (folder-input) — adds the bucket's source paths to the main watched directories
- **Delete** (trash) — removes the bucket and all its vector data

**Sidebar header:** The **New Bucket** button creates a fresh bucket. The **Import** button (upload icon) restores a bucket from a previously exported zip file.

**Files table:** Lists all files indexed in the bucket with their chunk counts. Click a file to open it in the viewer.

## Creating a Bucket

### From the UI

1. Go to the **Buckets tab**
2. Click **New Bucket** in the left sidebar
3. Enter a name, optional description, source path, glob pattern, expiration, and optional color
4. Click **Create**

### From the API

```json
POST /api/v1/buckets
{
  "name": "grpc-evaluation",
  "sources": [
    {"path": "/home/user/research/grpc-docs", "glob": "**/*.md"}
  ],
  "expires_in": 86400,
  "color": "#6366f1"
}
```

Sources accept absolute paths to files or directories. The `glob` pattern defaults to `**/*.md`. Set `expires_in` to auto-expire the bucket after that many seconds (minimum 60), or omit it for a permanent bucket. `color` accepts any hex color — if omitted, one is auto-assigned from the built-in palette.

**Docker:** If a source path isn't mounted into the container, MarkdownKB automatically adds it to `config/compose.override.yml` and returns `docker_restart_required: true`. Restart with `make docker-down && make docker-up` — the bucket will index on next startup. When a bucket is deleted, its mount is removed from `compose.override.yml` if no other bucket needs it.

Buckets are mounted more precisely than watched source directories. A watched source mounts an entire directory tree; a bucket mount covers only the specific path the bucket needs. This means that if you're using buckets for content you're less certain about — third-party docs, external references — Docker's mount boundary limits what any operation can reach to just that bucket's path. See [Write tool security](../reference/mcp-server.md#write-tool-security) for the full picture of what's bounded and what isn't.

## Editing a Bucket

Click the **pencil icon** in the bucket detail panel to enter edit mode. You can change:

- **Name** — rename the bucket
- **Expiration** — set or remove the expiration
- **Color** — pick from the built-in palette

Changes take effect immediately.

Via the API:
```json
PATCH /api/v1/buckets/{id}
{
  "name": "new-name",
  "expires_in": 604800,
  "color": "#ec4899"
}
```

Any combination of fields can be sent — only the fields present in the request are updated.

## Expiration

Buckets can be permanent (no `expires_in`) or set to expire:

- **Permanent** — stays until you explicitly delete it. The built-in docs bucket is permanent.
- **Expiring** — when the expiry time passes, the bucket is flagged as **expired** and stops being indexed. It is **not automatically deleted** — it remains visible in the UI with an "expired" badge until you delete it manually.

This means you won't silently lose a bucket you wanted to keep. Expired buckets are still browsable — their files and vector data remain intact.

**Settings panel history:** Settings > Buckets shows a sortable table of all buckets with their status (Active, Expiring soon, Expired). You can delete any bucket from this table, including expired ones. Bucket creation is on the Buckets tab — the Settings panel is management-only.

## Bucket Colors

Each bucket gets a color — auto-assigned from the palette on creation, or set explicitly. Colors appear in:

- The **Buckets tab sidebar** — colored dot next to each bucket name
- The **Doc Map** — bucket nodes use the bucket's color instead of a hardcoded red, making it easy to see which external documents belong to which bucket when multiple buckets are selected

The default palette cycles through indigo, violet, pink, orange, teal, cyan, lime, and amber.

## Using a Bucket

Select a bucket from the sidebar dropdown in Chat, Search, Planner, or Doc Map.

### Bucket Only

When a bucket is active with no scope selected, retrieval is limited to the bucket's documents. This is for focused work — understanding new material in isolation before mixing it with your existing knowledge.

### Bucket + Scope (Combined)

When both a bucket and a scope are active, results come from **both** — your permanent knowledge base (filtered by the scope) and the bucket's documents. Results are tagged by source so you can tell which answers come from your docs and which come from the bucket.

This is the most powerful mode. Use cases:

**Vendor evaluation.** Load vendor API docs into a bucket. Select your "Architecture" scope. Chat: "How does this vendor's authentication approach compare to what we already do?" The LLM has context from both — the vendor's docs and your architecture patterns — and can compare them directly.

**Research synthesis.** Load research papers or conference notes into a bucket. Select your "Research" scope. Search: "What in these new papers overlaps with my existing work?" Results come from both collections, ranked by relevance.

**Migration planning.** Load the new framework's documentation into a bucket. Select the scope covering your current implementation. Planner: "Plan a migration from our current auth system to the new one." The planner has context from both the destination (bucket) and the origin (scope).

**Doc Map overlap discovery.** Select a scope and a bucket in the Doc Map tab. Your permanent documents appear in their usual cluster colors. Bucket documents appear in the bucket's assigned color. Edges between them show where the external material connects to your existing knowledge.

## Adding Documents

You can add documents to an existing bucket without recreating it:

```json
POST /api/v1/buckets/{id}/add
{
  "sources": [{"path": "/home/user/more-docs", "glob": "**/*.md"}]
}
```

Duplicate files (same path) are skipped.

### Reading files back

You can read the full content of any bucket file (filesystem-sourced or pushed) via `GET /api/v1/buckets/{id}/file?path=...` or the `bucket_read_file` MCP tool. Content is reconstructed from stored chunks.

### Content push (no filesystem access)

Buckets can also be populated by pushing document content directly over the API, without any files on disk:

```json
POST /api/v1/buckets/{id}/documents
{
  "documents": [
    {"name": "api-reference.md", "content": "# API Reference\n\n..."}
  ]
}
```

Pushed documents exist only as vectors in ChromaDB with virtual paths like `bucket://bucket-name/api-reference.md`. This is designed for remote agents and integrations that cannot write files to the MarkdownKB host. The same capability is available via the `bucket_push` MCP tool.

## MCP Tools

When the buckets plugin is enabled, agents can create, search, and chat with buckets via MCP:

| Tool | Description |
|------|-------------|
| `bucket_create` | Create a bucket from source paths |
| `bucket_add` | Add documents to an existing bucket |
| `bucket_push` | Push documents by content (no filesystem needed) |
| `bucket_list` | List all buckets |
| `bucket_list_files` | List files in a bucket |
| `bucket_read_file` | Read full content of a bucket file |
| `bucket_search` | Search within a bucket |
| `bucket_chat` | RAG chat scoped to a bucket |
| `bucket_delete` | Delete a bucket |

Write tools (create, add, delete) respect the `mcp.read_only` flag, with an override via `mcp.allow_bucket_writes` — this allows bucket operations while keeping the main knowledge base read-only, since buckets are ephemeral and isolated.

## Configuration

```yaml
plugins:
  buckets:
    enabled: true
```

## Storage

Each bucket gets its own ChromaDB collection (`bucket_{id}`), stored alongside the main collection. Bucket metadata (name, description, sources, expiration, color) is in `{data_directory}/buckets.db`. File membership records (which files belong to which bucket) are also stored there, used to exclude bucket files from the Files tab. Deleting a bucket removes the DB record, the file memberships, and the ChromaDB collection.
