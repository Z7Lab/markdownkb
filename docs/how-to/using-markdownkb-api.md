# Using the MarkdownKB API

How to search, chat, write documents, and manage buckets programmatically — from scripts, AI agents, CI pipelines, or any HTTP client.

MarkdownKB exposes two interfaces: a **REST API** (port 9713) and an **MCP server** (port 9715). Both use the same backend. REST is for scripts and integrations; MCP is for AI agents.

## Authentication

When an API key is configured, all requests require it:

- **REST:** `X-MarkdownKB-Key: <key>` header
- **MCP:** `X-MarkdownKB-Key: <key>` header or `?token=<key>` query parameter

When no key is configured (default for localhost), authentication is disabled.

## Quick start (curl)

```bash
# Health check
curl -s http://localhost:9713/api/health | jq

# Search your knowledge base
curl -s -X POST http://localhost:9713/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "how does authentication work", "top_k": 5}' | jq

# Chat with your docs
curl -s -X POST http://localhost:9713/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain the plugin system"}' | jq

# List indexed files
curl -s http://localhost:9713/api/files | jq '.files | length'
```

## Quick start (Python)

```python
import json, urllib.request

BASE = "http://localhost:9713"
API_KEY = ""  # set if authentication is enabled

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-MarkdownKB-Key"] = API_KEY
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    return json.loads(urllib.request.urlopen(req).read())

# Search
results = api("POST", "/api/search", {"query": "deployment guide", "top_k": 5})
for r in results["results"]:
    print(f'{r["score"]:.2f}  {r["source_path"]}')

# Chat
resp = api("POST", "/api/chat", {"message": "What LLM providers are supported?"})
print(resp["response"])
```

## Core endpoints

### Search

```bash
# Basic search (hybrid vector + BM25)
POST /api/search
{"query": "kubernetes deployment", "top_k": 5}

# Search within a scope
POST /api/search
{"query": "auth flow", "scope_ids": "scope-id-1,scope-id-2"}

# Search within a bucket
POST /api/search
{"query": "vendor API reference", "bucket_id": "abc123"}

# Search with AI summary
POST /api/search/summarize
{"query": "how does rate limiting work", "top_k": 10}

# Deep research (MCTS multi-angle synthesis)
POST /api/search/summarize
{"query": "compare auth approaches", "deep_research": true, "deep_research_iterations": 5}
```

Response shape for `/api/search`:
```json
{
  "results": [
    {"document": "chunk text...", "source_path": "/path/to/file.md", "score": 0.87, "heading": "Section"},
    ...
  ],
  "query": "kubernetes deployment",
  "search_id": "srch_abc123"
}
```

### Chat

```bash
# Single-turn chat (returns complete response)
POST /api/chat
{"message": "Explain the plugin system"}

# Streaming chat (SSE — returns token-by-token)
POST /api/chat/stream
{"message": "How do scopes work?", "thread_id": "optional-thread-id"}

# Chat within a scope or bucket
POST /api/chat/stream
{"message": "Summarize the API docs", "scope_ids": "docs-scope", "bucket_id": "vendor-docs"}
```

Response for `/api/chat`:
```json
{
  "response": "The plugin system works by...",
  "sources": ["/path/to/file.md"],
  "source_map": {"[1]": "/path/to/file.md"}
}
```

Streaming `/api/chat/stream` returns SSE events: `thread`, `sources`, `token` (repeated), `done`.

### Files

```bash
# List all indexed files
GET /api/files

# Get file content and metadata
GET /api/file?path=/path/to/doc.md

# Check indexing status for a file
GET /api/file/status?path=/path/to/doc.md

# Re-index a single file
POST /api/files/reindex
{"path": "/path/to/doc.md"}

# Content search (find files by content, lightweight)
POST /api/files/search
{"query": "kubernetes", "top_k": 50}
```

### Sources

```bash
# List configured source directories
GET /api/sources

# Add a source directory (starts watching + indexing immediately)
POST /api/sources
{"path": "/home/user/docs"}

# Remove a source directory
DELETE /api/sources
{"path": "/home/user/docs", "cleanup": true}
```

### Scopes

```bash
# List scopes
GET /api/scopes

# Create a scope (filter searches to specific directories/tags)
POST /api/scopes
{"name": "Project Docs", "source_roots": ["/home/user/project/docs"]}
```

## Buckets

Buckets are temporary document collections — isolated from the main knowledge base. Use them for vendor docs, research material, or anything you want to search without mixing into your permanent KB.

```bash
# List buckets
GET /api/buckets

# Create a bucket from a directory (sources is optional — omit for an empty bucket)
POST /api/buckets
{"name": "vendor-api-docs", "sources": [{"path": "/tmp/vendor-docs", "glob": "**/*.md"}]}

# Search within a bucket
POST /api/buckets/{id}/search
{"query": "rate limiting", "top_k": 5}

# Chat with a bucket
POST /api/buckets/{id}/chat
{"message": "Summarize the authentication section"}

# Add more files to an existing bucket
POST /api/buckets/{id}/add
{"sources": [{"path": "/tmp/more-docs", "glob": "**/*.md"}]}

# Push documents by content (no filesystem access needed)
POST /api/buckets/{id}/documents
{"documents": [{"name": "file.md", "content": "# Markdown content..."}]}

# List files in a bucket
GET /api/buckets/{id}/files

# Read full content of a bucket file (reconstructed from chunks)
GET /api/buckets/{id}/file?path=bucket://bucket-name/file.md

# Set expiration (seconds from now, or null for permanent)
PATCH /api/buckets/{id}
{"expires_in": 86400}

# Delete a bucket
DELETE /api/buckets/{id}
```

## Writing documents

Requires `plugins.write_api.enabled: true` in settings.

```bash
# Create a new document
POST /api/documents
{
  "path": "notes/meeting-2026-04-09.md",
  "content": "# Meeting Notes\n\nKey decisions...",
  "overwrite": false
}

# Delete a document
DELETE /api/documents?path=notes/meeting-2026-04-09.md
```

When multiple source directories are configured, the `source` field is required — the API will return an error listing available sources. With a single source, it defaults to that source. The file watcher picks up new files and indexes automatically.

## MCP tools

Connect to the MCP server at `http://localhost:9715/mcp` (Streamable HTTP transport) or run `python mcp_server.py` for stdio.

### Core tools (always available)

| Tool | Description |
|------|-------------|
| `search` | Semantic search, returns chunks with scores |
| `search_documents` | Search and return full document content (for prompt embedding) |
| `get_file` | Get full content of a specific file |
| `list_files` | List all indexed files |
| `list_sources` | List configured source directories |
| `list_scopes` | List available scopes |
| `chat` | RAG chat with the knowledge base |
| `enhance_query` | LLM-powered query expansion |
| `stats` | Knowledge base statistics |
| `health` | Health check |
| `list_models` | List available embedding models |
| `list_threads` | List chat threads |
| `deep_research` | Multi-angle MCTS research synthesis |

### Write tools (require `mcp.read_only: false`)

| Tool | Additional flag | Description |
|------|----------------|-------------|
| `save_file` | `mcp.save_document` | Write a markdown file to a source directory |
| `delete_file` | `mcp.save_document` | Delete a markdown file |
| `index_file` | — | Re-index a single file |

### Plugin tools

| Tool | Plugin | Description |
|------|--------|-------------|
| `search_summarize` | search | Search with AI summary |
| `plan` | planner | Generate implementation plan via MCTS |
| `list_tags` | tags | List tags with counts |
| `generate_tags` | tags | AI-generate tags for a file (write) |
| `update_tags` | tags | Update tags on a file (write) |
| `export_chat` | export | Export conversation history |
| `docmap` | docmap | Get document similarity graph data |
| `query_knowledge_graph` | knowledge_graph | Query KG entities and relationships |
| `get_kg_entity` | knowledge_graph | Get entity details with relationships |
| `find_relationship_path` | knowledge_graph | BFS path between two entities |

### Bucket tools (require `buckets` plugin)

| Tool | Write | Description |
|------|-------|-------------|
| `bucket_list` | | List all buckets |
| `bucket_list_files` | | List files in a bucket |
| `bucket_read_file` | | Read full content of a bucket file |
| `bucket_search` | | Search within a bucket |
| `bucket_chat` | | Chat with a bucket |
| `bucket_create` | yes | Create a bucket from a directory |
| `bucket_add` | yes | Add files to an existing bucket |
| `bucket_push` | yes | Push documents by content (no filesystem needed) |
| `bucket_delete` | yes | Delete a bucket |

Bucket write tools can be allowed even with `mcp.read_only: true` by setting `mcp.allow_bucket_writes: true` — buckets are isolated from the main knowledge base.

## Useful patterns

### Agent research workflow

1. Create a bucket from downloaded docs: `bucket_create`
2. Search it: `bucket_search` or `bucket_chat`
3. Save findings to the permanent KB: `save_file`
4. Clean up: `bucket_delete`

### Incremental indexing

Files are indexed automatically when the file watcher detects changes. To force a re-index:

```bash
# Re-index everything
POST /api/index
{"force": true}

# Re-index a single file
POST /api/files/reindex
{"path": "/path/to/changed.md"}
```

### Checking what's indexed

```bash
# Stats overview
GET /api/stats

# Database sizes and counts
GET /api/settings/database-stats
```

## Error handling

- **401** — missing or invalid API key
- **404** — resource not found (file, bucket, scope, thread)
- **409** — conflict (file already exists without `overwrite: true`)
- **422** — validation error (bad request body)
- **503** — plugin not initialized (feature not enabled)

All error responses include a `detail` field with a human-readable message.
