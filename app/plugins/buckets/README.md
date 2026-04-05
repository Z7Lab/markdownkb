# Buckets Plugin

Temporary scoped document collections with independent vector storage, search, and RAG chat. Each bucket gets its own ChromaDB collection for isolated retrieval.

**Feature flag:** `buckets`
**Prefix:** `/api`

## Use Cases

- **Research workflows.** Ingest tutorial transcripts, GitHub `llms.txt` files, or conference notes. Search them in isolation. Delete when done.
- **Project-scoped context.** Create a bucket from a project's `docs/` directory. Chat and search stay within that project's documents.
- **Temporary investigations.** Pull in logs, incident reports, or design docs for a focused investigation without polluting the permanent knowledge base.
- **Evaluate new approaches.** Load docs about a new framework, library, or architecture into a bucket. Use the Planner to generate an implementation plan scoped to that bucket, then compare against your existing knowledge base.
- **Cross-reference external docs.** Create a bucket from vendor documentation or API specs. Chat with it to understand how it maps to your current system.

## Practical Examples

### Example 1: Evaluate a new framework

You're considering switching from REST to gRPC. Download the gRPC docs and create a bucket:

```bash
# Gather docs locally
mkdir -p ~/research/grpc-eval
# ... copy/download gRPC guides, migration docs, performance benchmarks ...

# Create the bucket
curl -X POST http://localhost:9713/api/buckets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "grpc-evaluation",
    "sources": [{"path": "/home/user/research/grpc-eval", "glob": "**/*.md"}],
    "expires_in": 86400
  }'
```

Then in the UI:
1. Go to **Planner** tab
2. Select **grpc-evaluation** from the Buckets dropdown in the sidebar
3. Enter: "Plan a migration from REST to gRPC for our payment gateway"
4. The planner generates a plan using only the gRPC docs as context

### Example 2: Incident investigation

Pull together incident-related docs for a focused review:

```bash
curl -X POST http://localhost:9713/api/buckets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "march-outage",
    "sources": [
      {"path": "/home/user/incidents/2026-03", "glob": "**/*.md"},
      {"path": "/home/user/projects/infra/runbooks", "glob": "**/database*.md"}
    ],
    "expires_in": 3600
  }'
```

Then in the **Chat** tab, select the bucket and ask: "What were the common root causes across these incidents, and which runbooks would have helped?"

### Example 3: Compare new docs against your knowledge base

1. Create a bucket with vendor API docs for a new integration
2. In the **Chat** tab, select the bucket and ask specific questions about the vendor's API
3. Switch back to **All sources** (deselect the bucket) and ask the same questions to see what your existing docs say
4. Use the **Planner** with the bucket selected to generate an integration plan based on the vendor docs

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/buckets` | List all buckets with metadata |
| POST | `/api/buckets` | Create a new bucket from source paths |
| GET | `/api/buckets/{id}` | Get bucket details |
| DELETE | `/api/buckets/{id}` | Delete a bucket and its vector data |
| POST | `/api/buckets/{id}/search` | Search within a bucket |
| POST | `/api/buckets/{id}/chat` | RAG chat scoped to a bucket |
| POST | `/api/buckets/{id}/add` | Add documents to an existing bucket (skips duplicates) |

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

## Bucket-Scoped Search, Chat, and Planning

Buckets integrate with search, chat, and planner endpoints. Pass `bucket_id` in the request body:

```json
POST /api/search
{"query": "authentication flow", "bucket_id": "a1b2c3d4e5f6"}

POST /api/chat/stream
{"message": "How does auth work?", "bucket_id": "a1b2c3d4e5f6"}

POST /api/planner/plan/stream
{"request": "Plan a migration to the new auth system", "bucket_id": "a1b2c3d4e5f6"}
```

When `bucket_id` is set, retrieval is scoped to the bucket's collection. Scope and tag filters are bypassed — the bucket is the scope.

In the web UI, select a bucket from the sidebar dropdown in the Chat, Search, or Planner tabs.

## Expiration and Cleanup

Expired buckets are automatically cleaned up in two places:

1. **On server startup** — all expired buckets are deleted before the app begins serving requests.
2. **On list** — the `GET /api/buckets` endpoint cleans up any expired buckets before returning results, so the UI never shows stale buckets.

Cleanup deletes both the SQLite metadata row and the bucket's ChromaDB collection.

## MCP Tools

When the buckets plugin is enabled, seven MCP tools are registered:

| Tool | Write | Description |
|------|-------|-------------|
| `bucket_create` | yes | Create a bucket from source paths |
| `bucket_add` | yes | Add documents to an existing bucket |
| `bucket_list` | | List all buckets |
| `bucket_list_files` | | List files and chunk counts in a bucket |
| `bucket_search` | | Search within a bucket |
| `bucket_chat` | | RAG chat scoped to a bucket |
| `bucket_delete` | yes | Delete a bucket and its vector data |

Write tools are disabled when `mcp.read_only` is true, unless `mcp.allow_bucket_writes` is also true — this allows bucket operations while keeping the main knowledge base read-only.

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
