# MCP Server

MarkdownKB includes a standalone MCP (Model Context Protocol) server that exposes core knowledge base capabilities to any MCP-compatible client — Claude Desktop, the personal-dispatcher, or custom agents.

The server runs as a **separate process** alongside the FastAPI app. It imports core services directly (no HTTP proxy), sharing the same `config/settings.yaml`, vector store, and SQLite databases.

## All MCP Tools at a Glance

35 tools organized by category. Core tools are always available; plugin tools appear when their plugin is enabled.

**Search & Retrieval:**
- `search` — hybrid vector + keyword search, returns chunks with source paths
- `search_documents` — search and return full document content (deduplicated by file)
- `search_summarize` — search and return an LLM-generated summary *(search plugin)*
- `deep_research` — multi-angle MCTS research synthesis
- `enhance_query` — extract keywords and expand acronyms for better retrieval

**Chat & Conversation:**
- `chat` — RAG Q&A grounded in your knowledge base, with source citations
- `list_threads` — list recent chat threads
- `export_chat` — export conversations as markdown or JSON *(export plugin)*

**Documents & Files:**
- `get_file` — read a file by path (use after search/chat to read cited sources in full)
- `list_files` — list all indexed files
- `index_file` — re-index a single markdown file *(write)*
- `save_file` — save a markdown file to a watched source directory *(write)*
- `delete_file` — delete a markdown file from the knowledge base *(write)*

**Planning:**
- `plan` — generate an implementation plan using MCTS *(planner plugin)*

**Scopes & Tags:**
- `list_scopes` — list named scopes (folder + tag filter presets)
- `list_tags` — list all tags with file counts *(tags plugin)*
- `generate_tags` — generate tags for a file using AI *(tags plugin, write)*
- `update_tags` — set, add, or remove tags on a file *(tags plugin, write)*

**Visualization:**
- `docmap` — compute document similarity map — nodes, edges, clusters *(docmap plugin)*
- `query_knowledge_graph` — query entities and typed relationships *(knowledge_graph plugin)*
- `get_kg_entity` — get entity details with relationships *(knowledge_graph plugin)*
- `find_relationship_path` — BFS shortest path between entities *(knowledge_graph plugin)*

**Buckets (temporary collections):**
- `bucket_create` — create a bucket from source paths *(buckets plugin, write)*
- `bucket_list` — list all buckets *(buckets plugin)*
- `bucket_list_files` — list files in a bucket *(buckets plugin)*
- `bucket_read_file` — read full content of a bucket file *(buckets plugin)*
- `bucket_search` — search within a bucket *(buckets plugin)*
- `bucket_chat` — RAG chat scoped to a bucket *(buckets plugin)*
- `bucket_add` — add documents to a bucket *(buckets plugin, write)*
- `bucket_push` — push documents by content, no filesystem needed *(buckets plugin, write)*
- `bucket_delete` — delete a bucket *(buckets plugin, write)*

**System:**
- `health` — server health, chunk count, active LLM provider
- `list_sources` — list configured source directories
- `list_models` — list LLM providers and active model
- `stats` — knowledge base statistics

## Quick Start

```bash
# Streamable HTTP transport via Makefile (recommended for local dev)
make mcp

# stdio transport (for Claude Desktop, pipes, etc.)
.venv/bin/python mcp_server.py

# Streamable HTTP transport (manual)
.venv/bin/python mcp_server.py --http --port 9715
```

## Detailed Tool Reference

| Tool | Maps to | Plugin | Write | Description |
|------|---------|--------|-------|-------------|
| `health` | `app/routers/health` | core | | Server health, chunk count, active LLM provider |
| `search` | `app/rag/retriever` | core | | Hybrid vector + keyword search, returns chunks with source paths. Use `get_file` to read full docs. |
| `search_documents` | `app/rag/retriever` | core | | Search and return full document content (deduplicated by file) |
| `enhance_query` | `app/services/query_service` | core | | Extract keywords and expand acronyms for better retrieval |
| `chat` | `app/routers/chat` | core | | RAG Q&A — answer includes `sources` list of file paths used as context |
| `get_file` | `app/routers/files` | core | | Read a file by path — use after `search` or `chat` to read cited sources in full |
| `list_files` | `app/routers/files` | core | | List all indexed files (optionally filter by status) |
| `list_threads` | `app/routers/threads` | core | | List recent chat threads |
| `list_sources` | `app/routers/sources` | core | | List configured source directories |
| `list_models` | `app/services/llm_service` | core | | List LLM providers and active model |
| `list_scopes` | `app/storage/scopedb` | core | | List named scopes (folder + tag filter presets) |
| `stats` | `app/routers/maintenance` | core | | Knowledge base statistics |
| `deep_research` | `app/services/deep_research` | core | | Multi-angle MCTS research synthesis |
| `index_file` | `app/ingestion/` | core | yes | Re-index a single markdown file |
| `save_file` | `app/routers/files` | core | yes | Save a markdown file to a watched source directory |
| `delete_file` | `app/mcp/tools/` | core | yes | Delete a markdown file from the knowledge base |
| `search_summarize` | `app/services/` | search | | Search and return an LLM-generated summary |
| `plan` | `app/services/planner_service` | planner | | Generate an implementation plan using MCTS |
| `list_tags` | `app/plugins/tags/tagdb` | tags | | List all tags with file counts, or tags for a specific file |
| `generate_tags` | `app/lib/tag_generator/` | tags | yes | Generate tags for a file using AI |
| `update_tags` | `app/plugins/tags/tagdb` | tags | yes | Set, add, or remove tags on a file |
| `docmap` | `app/services/graph_service` | docmap | | Compute document similarity map — nodes, edges, clusters |
| `query_knowledge_graph` | `app/storage/knowledgegraph` | knowledge_graph | | Query entities and typed relationships (filter by type) |
| `get_kg_entity` | `app/storage/knowledgegraph` | knowledge_graph | | Get entity details with all incoming/outgoing relationships |
| `find_relationship_path` | `app/storage/knowledgegraph` | knowledge_graph | | BFS shortest path between two entities |
| `export_chat` | `app/storage/chatdb` | export | | Export chat conversations as markdown or JSON |
| `bucket_create` | `app/plugins/buckets/` | buckets | yes | Create a temporary bucket from source paths |
| `bucket_list` | `app/plugins/buckets/` | buckets | | List all temporary buckets with metadata |
| `bucket_search` | `app/plugins/buckets/` | buckets | | Search within a temporary bucket |
| `bucket_chat` | `app/plugins/buckets/` | buckets | | RAG chat scoped to a temporary bucket |
| `bucket_delete` | `app/plugins/buckets/` | buckets | yes | Delete a temporary bucket and its vector data |
| `bucket_add` | `app/plugins/buckets/` | buckets | yes | Add documents to an existing bucket |
| `bucket_push` | `app/plugins/buckets/` | buckets | yes | Push documents by content (no filesystem needed) |
| `bucket_list_files` | `app/plugins/buckets/` | buckets | | List files and chunk counts in a bucket |
| `bucket_read_file` | `app/plugins/buckets/` | buckets | | Read full content of a bucket file (reconstructed from chunks) |

**Gating rules:**
- **core** tools are always registered (unless they're write tools and `mcp.read_only` is true)
- **Plugin** tools require `plugins.<name>.enabled: true` in settings
- **Write** tools are disabled when `mcp.read_only: true`, regardless of other flags
- `save_file` and `delete_file` have an additional feature flag: `mcp.save_document` must also be true
- **Bucket write exemption:** when `mcp.allow_bucket_writes: true`, bucket write tools (`bucket_create`, `bucket_delete`, `bucket_add`, `bucket_push`) are allowed even with `read_only: true`. Buckets are ephemeral and isolated — they don't touch the main knowledge base.

### search

```
search(query: "authentication flow", top_k: 5)
→ {results: [{content, source, score}, ...], total}

search(query: "authentication flow", top_k: 5, tags: ["security", "backend"])
→ {results: [...], total, tags_filter: ["security", "backend"]}

search(query: "authentication flow", scope_id: "abc123def456")
→ {results: [...], total, scope_id: "abc123def456"}
```

Optionally filter results by tags (OR logic — documents matching any tag are included), scope, or both. Use `list_tags` to discover available tags and `list_scopes` to discover available scopes. When both `scope_id` and `tags` are provided, they are combined.

### search_documents

```
search_documents(query: "authentication flow", top_k: 3, max_chars: 15000)
→ {documents: [{path, title, content, score}, ...], total_chars}

search_documents(query: "authentication flow", scope_id: "abc123def456")
→ {documents: [...], total_chars, scope_id: "abc123def456"}
```

Unlike `search` which returns individual chunks, this returns the **full content** of the top matching files (deduplicated by source path). Ideal for embedding complete documents into prompts. The `max_chars` budget prevents oversized responses — documents are included in score order until the budget is exhausted, with truncation if needed. Accepts `scope_id` and `tags` for filtering.

### plan

```
plan(request: "Design a caching layer for the API", iterations: 3, n_approaches: 3, save: true)
→ {plan: "...", approaches: [{content, score}, ...], plan_id: "abc123"}

plan(request: "Design a caching layer", scope_id: "abc123def456")
→ {plan: "...", approaches: [...], plan_id: "..."}
```

Uses MCTS to explore multiple approaches grounded in your knowledge base, then synthesizes the best plan. Plans are saved to the plan database by default (visible in the Planner tab sidebar with a bot icon). Set `save: false` to skip persistence. Accepts `scope_id` to restrict research to specific folders/tags.

### chat

```
chat(message: "How does the auth middleware work?")
→ {response: "The auth middleware checks...", sources: [...], source_map: {...}}

chat(message: "How does the auth middleware work?", scope_id: "abc123def456")
→ {response: "...", sources: [...], source_map: {...}, scope_id: "abc123def456"}

chat(message: "Tell me more about the token flow", thread_id: "a1b2c3d4e5f6")
→ {response: "...", sources: [...], source_map: {...}, thread_id: "a1b2c3d4e5f6"}
```

Uses the same RAG pipeline as the web UI chat — retrieves relevant chunks, builds a context prompt, and calls the active LLM provider. Accepts `scope_id` for filtering. Pass `thread_id` from a previous response to continue a multi-turn conversation with history (requires `mcp.track_history: true`).

### get_file

```
get_file(path: "/home/user/docs/auth.md")
→ {path, content, status, chunk_count}
```

Only reads files within configured source directories. Returns an error for paths outside sources or unindexed files.

### list_files

```
list_files(status: "complete")
→ {files: [{path, status, chunk_count}, ...], total}
```

Status filter is optional. Valid values: `complete`, `pending`, `error`.

### save_file

```
save_file(
  path: "captures/2026-03-15-meeting.md",
  content: "# Meeting Notes\n\n...",
  source: "",       # defaults to first configured source
  overwrite: false
)
→ {status: "created", path, relative_path, source}
```

Path must be relative, must end in `.md`, and cannot contain `..` traversal. The file is written to disk and automatically picked up by the file watcher for indexing.

**Disabled by default.** Enable in `config/settings.yaml`:

```yaml
mcp:
  save_document: true
```

### delete_file

```
delete_file(path: "/home/user/docs/notes/outdated.md")
→ {status: "deleted", path}
```

Removes the file from disk, vector store, and tracking database. Path must be within a configured source directory. Gated by the same `mcp.save_document` flag as `save_file`.

### index_file

```
index_file(path: "/home/user/docs/new-file.md")
→ {status, chunk_count, path}
```

Re-indexes the file (parse → embed → store). File must be within a configured source directory and end in `.md`.

### list_sources

```
list_sources()
→ {sources: ["/home/user/docs", "/home/user/notes"]}
```

### stats

```
stats()
→ {total_files, complete, pending, error, total_chunks, vector_count}
```

### bucket_create

```
bucket_create(
  name: "project-docs",
  sources: [{"path": "/home/user/projects/myapp/docs", "glob": "**/*.md"}],
  expires_in: 3600
)
→ {id, name, file_count, chunk_count, created_at, expires_at}
```

Creates a temporary bucket with its own ChromaDB collection. Each source must have a `path` (file or directory) and an optional `glob` pattern (default `**/*.md`). `expires_in` is optional (seconds until auto-delete).

### bucket_search

```
bucket_search(bucket: "project-docs", query: "authentication", top_k: 5)
→ {results: [{content, source, score}, ...], total}
```

### bucket_chat

```
bucket_chat(bucket: "project-docs", message: "How does auth work?")
→ {response: "...", sources: [...], source_map: {...}}
```

### bucket_list

```
bucket_list()
→ {buckets: [{id, name, file_count, chunk_count, created_at, expires_at}, ...]}
```

### bucket_add

```
bucket_add(
  bucket: "project-docs",
  sources: [{"path": "/home/user/projects/myapp/tests", "glob": "**/*.md"}]
)
→ {bucket_id, bucket_name, added_files, added_chunks, skipped_files, total_files, total_chunks}
```

Add documents to an existing bucket without recreating it. Files already present in the bucket are skipped automatically.

### bucket_list_files

```
bucket_list_files(bucket: "project-docs")
→ {bucket_id, bucket_name, files: [{path, name, chunk_count}, ...], total_files, total_chunks}
```

List all files indexed in a bucket with their chunk counts.

### bucket_read_file

```
bucket_read_file(bucket: "project-docs", path: "bucket://project-docs/api-reference.md")
→ {bucket_id, bucket_name, path, content}
```

Read the full content of a file in a bucket. The content is reconstructed from stored chunks. Works for both filesystem-sourced and pushed (virtual) documents.

### bucket_push

```
bucket_push(
  bucket: "project-docs",
  documents: [
    {"name": "api-reference.md", "content": "# API Reference\n\n..."},
    {"name": "changelog.md", "content": "# Changelog\n\n## v2.0\n\n..."}
  ]
)
→ {bucket_id, bucket_name, added_files, added_chunks, total_files, total_chunks}
```

Push documents by content without filesystem access. Each document needs a `name` and `content` field. Documents are stored as vectors in ChromaDB with virtual paths like `bucket://bucket-name/api-reference.md` — they never exist on disk. This is designed for remote agents that cannot write files to the MarkdownKB host.

### bucket_delete

```
bucket_delete(bucket: "project-docs")
→ {deleted: true, id, name}
```

## Transports

| Transport | Flag | Use case |
|-----------|------|----------|
| **stdio** | (default) | Claude Desktop, subprocess pipes, local agents |
| **Streamable HTTP** | `--http` | Network clients, remote agents |

### stdio (default)

The server reads JSON-RPC messages from stdin and writes responses to stdout. Logs go to stderr. This is the standard transport for Claude Desktop and similar tools.

### Streamable HTTP

```bash
.venv/bin/python mcp_server.py --http --host 0.0.0.0 --port 9715
```

| Flag | Default | Description |
|------|---------|-------------|
| `--http` | off | Enable Streamable HTTP transport |
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `9715` | Listen port |

## Claude Desktop Configuration

Add to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "markdownkb": {
      "command": "/path/to/markdownkb/.venv/bin/python",
      "args": ["/path/to/markdownkb/mcp_server.py"],
      "cwd": "/path/to/markdownkb"
    }
  }
}
```

## Docker

The MCP server runs as a separate service in `compose.yml`:

```bash
make up          # starts both markdownkb and markdownkb-mcp
make logs        # tails logs for both services
```

The `markdownkb-mcp` service uses Streamable HTTP transport on port 9715 (configurable via `MARKDOWNKB_MCP_PORT`). It shares the same data volume and config as the main app.

Connect from another service on the Docker network:

```
http://markdownkb-mcp:9715/mcp
```

Or from the host:

```
http://localhost:9715/mcp
```

## Architecture

The MCP server shares the same storage as the FastAPI app:

- **Config**: Reads `config/settings.yaml` via the same `Settings` singleton
- **Vector store**: ChromaDB at `{data_directory}/chromadb/`
- **Tracking DB**: SQLite at `{data_directory}/markdownkb.db`
- **Embeddings**: Same ONNX models, same embedding pipeline

On startup, the server loads embedding models (`load_models()`), initializes its own instances of `VectorStore`, `TrackingDB`, and `Retriever`, then auto-discovers and registers MCP tools. If the vector store is empty, it runs an initial index automatically.

DNS rebinding protection is disabled so that containers (e.g. sandbox agents) can reach the MCP server via `host.docker.internal`.

### Tool Auto-Discovery

Tools are auto-discovered from `app/mcp/tools/`. Each tool module exports:

- `TOOL` dict — with `name` (str), optional `feature_flag` (str or None), optional `requires_plugin` (str or None), and optional `write` (bool)
- `handler` callable — the MCP tool function

Three gating mechanisms control whether a tool is registered:

1. **`feature_flag`** — key under `mcp:` in settings. Tool disabled when the flag is `false`.
2. **`requires_plugin`** — plugin name (e.g. `"planner"`). Tool disabled when `plugins.<name>.enabled` is `false`. This keeps MCP tools in sync with their corresponding plugins — disabling the planner plugin also disables the MCP `plan` tool.
3. **`write: True`** — tool disabled when `mcp.read_only` is `true`, regardless of other flags. Exception: bucket write tools are allowed when `mcp.allow_bucket_writes: true`.

To add a new MCP tool, create a new `.py` file in `app/mcp/tools/` following the existing pattern.

### Scope Support

The `search`, `search_documents`, `chat`, `plan`, and `deep_research` tools accept an optional `scope_id` parameter. Scopes are named filter presets (folder paths + tags) managed via `POST /api/scopes`. Use the `list_scopes` tool to discover available scopes.

Scope resolution is handled by `app/mcp/scope.py`, which resolves the scope ID to `folders_filter` and `allowed_paths` parameters for the Retriever. Tag resolution calls `TagDB.get_paths_for_tags()` directly (not through the `tag_utils` callback which is only registered in the FastAPI process).

## Authentication

When an API key is configured (via `secrets/markdownkb_api_key` or `MARKDOWNKB_API_KEY` env var), the MCP Streamable HTTP server requires authentication. Three methods are accepted (checked in order):

1. **`Authorization: Bearer <key>`** header (preferred — key not visible in access logs)
2. **`X-MarkdownKB-Key: <key>`** header (same as the REST API)
3. **`?token=<key>`** query parameter (legacy fallback — key appears in server logs, avoid for new integrations)

If no API key is configured, all connections are allowed. The stdio transport is never authenticated.

Connect with auth:
```
# Preferred (Bearer)
Authorization: Bearer YOUR_KEY

# Legacy (query parameter)
http://localhost:9715/mcp?token=YOUR_KEY
```

> **Note**: The MCP server and FastAPI app can run simultaneously — SQLite uses WAL mode for safe concurrent reads. However, only one process should write to the vector store at a time to avoid conflicts.
