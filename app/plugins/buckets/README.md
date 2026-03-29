# Buckets Plugin

Temporary scoped document collections with independent vector storage, search, and RAG chat. Each bucket gets its own ChromaDB collection for isolated retrieval.

**Feature flag:** `buckets`
**Prefix:** `/api`

## Use Cases

- **Research workflows.** Ingest tutorial transcripts, GitHub `llms.txt` files, or conference notes. Search them in isolation. Delete when done.
- **Project-scoped context.** Create a bucket from a project's `docs/` directory. Chat and search stay within that project's documents.
- **Temporary investigations.** Pull in logs, incident reports, or design docs for a focused investigation without polluting the permanent knowledge base.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/buckets` | List all buckets with metadata |
| POST | `/api/buckets` | Create a new bucket from source paths |
| GET | `/api/buckets/{id}` | Get bucket details |
| DELETE | `/api/buckets/{id}` | Delete a bucket and its vector data |
| POST | `/api/buckets/{id}/search` | Search within a bucket |
| POST | `/api/buckets/{id}/chat` | RAG chat scoped to a bucket |

## Creating a Bucket

```json
POST /api/buckets
{
  "name": "project-docs",
  "sources": [
    {"path": "/home/user/projects/myapp/docs", "glob": "**/*.md"}
  ],
  "expires_in": 3600
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `name` | (required) | Unique display name |
| `sources` | (required) | List of `{path, glob}` source descriptors. `path` is an absolute path to a file or directory. `glob` defaults to `**/*.md`. |
| `expires_in` | null | Optional auto-delete after this many seconds (minimum 60) |

Sources are scanned, parsed, chunked, and embedded into a bucket-specific ChromaDB collection at creation time. The response includes `file_count` and `chunk_count`.

## Bucket-Scoped Search and Chat

Buckets integrate with the existing search and chat endpoints. Pass `bucket_id` in the request body:

```json
POST /api/search
{"query": "authentication flow", "bucket_id": "a1b2c3d4e5f6"}

POST /api/chat/stream
{"message": "How does auth work?", "bucket_id": "a1b2c3d4e5f6"}
```

When `bucket_id` is set, retrieval is scoped to the bucket's collection. Scope and tag filters are bypassed — the bucket is the scope.

In the web UI, select a bucket from the sidebar dropdown in the Chat or Search tabs.

## Expiration and Cleanup

Buckets with an `expires_at` timestamp are automatically cleaned up on server startup. The cleanup deletes both the SQLite metadata row and the ChromaDB collection.

There is no background expiration timer — expired buckets are cleaned up on the next server start. To force cleanup, restart the container or delete the bucket manually.

## MCP Tools

When the buckets plugin is enabled, five MCP tools are registered:

| Tool | Write | Description |
|------|-------|-------------|
| `bucket_create` | yes | Create a bucket from source paths |
| `bucket_list` | | List all buckets |
| `bucket_search` | | Search within a bucket |
| `bucket_chat` | | RAG chat scoped to a bucket |
| `bucket_delete` | yes | Delete a bucket and its vector data |

Write tools are disabled when `mcp.read_only` is true.

## Configuration

No plugin-specific configuration beyond `enabled`:

```yaml
plugins:
  buckets:
    enabled: true
```

## Storage

- **BucketDB** (`data/buckets.db`) — SQLite database for bucket metadata (name, sources, file/chunk counts, expiration).
- **ChromaDB collections** — one per bucket, named `bucket_{id}`. Stored alongside the main collection in `data/chromadb/`.

## Dependencies

- `app.ingestion.parser` — markdown parsing and chunking
- `app.embeddings.embedder` — vector embedding (same ONNX models as main index)
- `app.storage.vectorstore` — ChromaDB wrapper
- `app.rag.retriever` — hybrid search (used for bucket search and chat)
- `app.services.chat_service` — RAG chat pipeline (used for bucket chat)
