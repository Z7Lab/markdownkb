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

On first startup, mdkb creates a permanent **"mdkb Documentation"** bucket containing its own documentation. You can chat with it to learn the system:

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

## Creating a Bucket

### From the UI

1. Go to any tab with a sidebar (Chat, Search, Planner)
2. In the **Bucket** section, click **Create**
3. Enter a name and source paths
4. Optionally set an expiration time

### From the API

```json
POST /api/buckets
{
  "name": "grpc-evaluation",
  "sources": [
    {"path": "/home/user/research/grpc-docs", "glob": "**/*.md"}
  ],
  "expires_in": 86400
}
```

Sources accept absolute paths to files or directories. The `glob` pattern defaults to `**/*.md`. Set `expires_in` to auto-delete the bucket after that many seconds (minimum 60), or omit it for a permanent bucket.

## Using a Bucket

Select a bucket from the sidebar dropdown in Chat, Search, or Planner. When a bucket is active:

- **Chat** answers questions using only the bucket's documents
- **Search** returns results from only the bucket's documents
- **Planner** generates plans grounded in only the bucket's documents

Scope and tag filters are bypassed when a bucket is active — the bucket IS the scope.

### Comparing Against Your Knowledge Base

A powerful workflow:

1. Create a bucket with external docs (vendor API, new framework, research papers)
2. Chat with the bucket to understand the new material
3. Deselect the bucket and ask the same questions against your permanent knowledge base
4. Compare the answers — where does your existing knowledge overlap? Where are the gaps?

This is what the [philosophy doc](philosophy.md#convert-dont-connect) describes as temporary input for synthesis: the bucket is disposable, but the insights you extract from comparing it against your own documents can be captured as permanent markdown.

## Adding Documents

You can add documents to an existing bucket without recreating it:

```json
POST /api/buckets/{id}/add
{
  "sources": [{"path": "/home/user/more-docs", "glob": "**/*.md"}]
}
```

Duplicate files (same path) are skipped.

## Expiration

Buckets can be permanent (no `expires_in`) or auto-expiring:

- **Permanent** — stays until you delete it. The built-in docs bucket is permanent.
- **Auto-expiring** — deleted automatically after the specified duration. Cleanup runs on startup and when the bucket list is loaded.

## MCP Tools

When the buckets plugin is enabled, agents can create, search, and chat with buckets via MCP:

| Tool | Description |
|------|-------------|
| `bucket_create` | Create a bucket from source paths |
| `bucket_add` | Add documents to an existing bucket |
| `bucket_list` | List all buckets |
| `bucket_list_files` | List files in a bucket |
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

Each bucket gets its own ChromaDB collection (`bucket_{id}`), stored alongside the main collection. Bucket metadata (name, sources, expiration) is in `{data_directory}/buckets.db`. Deleting a bucket removes both the DB record and the ChromaDB collection.
