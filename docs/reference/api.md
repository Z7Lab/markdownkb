# API Reference

All endpoints under `http://localhost:9713/api/`. Interactive docs (Swagger UI) at `http://localhost:9713/docs`.

## Authentication

When an API key is configured (via Docker secret `markdownkb_api_key` or `MARKDOWNKB_API_KEY` env var), all `/api/*` endpoints require the header:

```
X-MarkdownKB-Key: <your-key>
```

Missing or invalid keys return **401 Unauthorized**. `/api/health` is always public (no key required). When no key is configured, authentication is disabled.

## Health & Stats

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/health/llm` | Lightweight LLM health check (for status polling) |
| GET | `/api/stats` | Index statistics (files, chunks, embedding model, provider) |

## Search

Requires the `search` feature flag. Plugin: `app/plugins/search/`.

Supports Google-style quoted phrases: `"exact phrase"` requires literal match in chunk content. Unquoted terms use semantic (vector) search. Configurable via `plugins.search` in settings.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/search` | Semantic search with optional query enhancement. Pass `bucket_id` to search within a specific bucket. |
| GET | `/api/searches` | List search history (paginated) |
| GET | `/api/searches/{id}/load` | Load historical search version with preserved results |
| GET | `/api/searches/{id}/versions` | Get all versions of a search (original + re-queries) |
| GET | `/api/searches/{id}/compare` | Compare historical search against current KB state |
| DELETE | `/api/searches/{id}` | Delete a search from history |
| POST | `/api/search/summarize` | AI summary of search results (streaming). Pass `deep_research: true` for MCTS-powered multi-angle synthesis (requires `deep_research` feature flag). |
| POST | `/api/search/enhance-query` | LLM query enhancement (keywords, acronyms) |

## Chat

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | RAG chat (non-streaming) |
| POST | `/api/chat/stream` | SSE streaming chat. Pass `bucket_id` to chat within a specific bucket. |
| DELETE | `/api/chat/history` | Clear conversation |
| POST | `/api/chat/save-plan` | Save response as markdown |

## Threads

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/threads` | List chat threads (paginated) |
| GET | `/api/threads/{id}/messages` | Get messages for a thread |
| DELETE | `/api/threads/{id}` | Delete a thread |
| PATCH | `/api/threads/{id}` | Rename a thread |

## Files

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/files` | List all discovered files (paginated) |
| GET | `/api/file` | Read file content |
| GET | `/api/file/status` | Get status of a single file |
| GET | `/api/folders` | List unique folders from indexed documents |
| PUT | `/api/files/toggle-rag` | Toggle RAG inclusion for a file |
| POST | `/api/files/search` | Content-based file search (returns file paths). Supports quoted exact phrases. |
| POST | `/api/files/unindex` | Remove file chunks from index |
| POST | `/api/files/index` | Index a single file |
| POST | `/api/files/reindex` | Re-embed a file's chunks |
| POST | `/api/files/unindex-source` | Unindex all files under a source directory |

## Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings` | Get full settings |
| GET | `/api/sources` | List source directories |
| POST | `/api/sources` | Add source directory (immediately starts watching + indexing) |
| DELETE | `/api/sources` | Remove source directory (with optional `cleanup` to unindex files) |
| POST | `/api/ignore-patterns` | Add ignore pattern |
| DELETE | `/api/ignore-patterns` | Remove ignore pattern |
| GET | `/api/project-roots` | List project root configurations |
| POST | `/api/project-roots` | Add project root (path + include/exclude patterns) |
| PUT | `/api/project-roots` | Update project root patterns |
| DELETE | `/api/project-roots` | Remove project root (with optional `cleanup` to unindex) |
| PUT | `/api/settings/provider` | Save LLM provider config (name, model, api_base, api_key) |
| PUT | `/api/settings/llm-params` | Save generation parameters (temperature, max_tokens, num_ctx) |
| POST | `/api/settings/test-connection` | Test LLM connectivity |
| POST | `/api/settings/ping-model` | Ping a specific model |
| POST | `/api/settings/refresh-models` | Fetch model list from provider |
| POST | `/api/settings/test-prompt` | Test a prompt with the LLM (streaming) |
| POST | `/api/settings/model-info` | Get model details |
| PUT | `/api/settings/features` | Toggle feature flag |
| PUT | `/api/settings/system-prompt` | Update system prompt |
| PUT | `/api/settings/intelligent-search` | Toggle intelligent search |
| PUT | `/api/settings/search-summary-prompt` | Update search summary prompt |
| PUT | `/api/settings/retrieval` | Update retrieval settings |
| GET | `/api/settings/plugins/{name}` | Get plugin configuration |
| PUT | `/api/settings/plugins/{name}` | Update plugin configuration (shallow merge) |
| GET | `/api/settings/log-level` | Get current log level |
| PUT | `/api/settings/log-level` | Set log level (`INFO`, `DEBUG`, or `OFF`) |
| GET | `/api/settings/logs` | Get log entries (incremental via `?since=`) |
| DELETE | `/api/settings/logs` | Clear log buffer |
| GET | `/api/settings/presets` | List retrieval presets |
| POST | `/api/settings/presets` | Create preset (name + settings, or snapshot current) |
| PUT | `/api/settings/presets/{id}` | Update preset name/settings |
| DELETE | `/api/settings/presets/{id}` | Delete preset |
| POST | `/api/settings/presets/{id}/load` | Apply preset to active retrieval config |

## Plugin Management

Core router (always registered). Manages plugin discovery, installation, and removal.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/plugins` | List all plugins (builtin + external) with manifests, plus core feature flags |
| GET | `/api/plugins/{name}` | Get details for a specific plugin |
| POST | `/api/plugins/install` | Install plugin from GitHub URL (`{ url }`) |
| DELETE | `/api/plugins/{name}` | Uninstall an external plugin (builtin plugins cannot be removed) |

### GET /api/plugins response

```json
{
  "plugins": [
    {
      "name": "search",
      "display_name": "Search & Summaries",
      "description": "...",
      "version": "1.0.0",
      "author": "markdownkb",
      "icon": "search",
      "category": "search",
      "feature_flag": "search",
      "enabled": true,
      "source": "builtin",
      "endpoints": [...],
      "config_schema": {...},
      "config": {...},
      "has_manifest": true
    }
  ],
  "core_features": [
    {
      "name": "rag_chat",
      "display_name": "RAG Chat",
      "enabled": true,
      "category": "core"
    }
  ]
}
```

### POST /api/plugins/install

Accepts GitHub URLs in several formats:
- `https://github.com/user/repo`
- `https://github.com/user/repo/tree/main/path/to/plugin`
- `user/repo`

The plugin must contain `__init__.py` with `FEATURE_FLAG` and `router` exports. A `plugin.yaml` manifest is recommended. If `requirements.txt` is present, dependencies are installed automatically.

## MCP Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings/mcp` | Get all MCP tool configurations |
| GET | `/api/settings/mcp/{tool}` | Get config for a specific MCP tool |
| PATCH | `/api/settings/mcp` | Update MCP tool configuration |

## Database Maintenance

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings/database-stats` | Stats for all databases |
| POST | `/api/settings/database/clear-chats` | Clear chat history |
| POST | `/api/settings/database/clear-searches` | Clear search history |
| POST | `/api/settings/database/clear-vectors` | Clear vector DB and file tracking |
| POST | `/api/settings/database/compact-chats` | Compact chat database |
| POST | `/api/settings/database/compact-searches` | Compact search database |

## Scopes

Named subsets of your knowledge base. Scopes can filter by folders, tags, or both. Pass a scope to Search, Chat, and Planner to restrict retrieval.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/scopes` | List all scopes |
| POST | `/api/scopes` | Create a scope (`{ name, folders[], tags[] }`) |
| GET | `/api/scopes/{id}` | Get a scope by ID |
| PUT | `/api/scopes/{id}` | Update a scope (`{ name, folders[], tags[] }`) |
| DELETE | `/api/scopes/{id}` | Delete a scope |

A scope requires at least one folder or tag. When resolved, folder filtering restricts by source path prefix; tag filtering uses OR logic (documents matching any listed tag are included). Both can be combined.

Search, Chat, and Planner endpoints accept an optional `scope_id` field in their request bodies. When provided, retrieval is restricted to the scope's folders and/or tags.

MCP tools (`search`, `search_documents`, `chat`, `plan`, `deep_research`) also accept a `scope_id` parameter for the same behavior. Use the `list_scopes` MCP tool to discover available scopes. See [MCP Server](mcp-server.md#scope-support) for details.

## Embeddings & Indexing

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings/embedding-models` | List embedding models + install status |
| GET | `/api/settings/embedding-models/status` | Poll background reindex progress |
| POST | `/api/settings/embedding-models/install` | Download an embedding model |
| PUT | `/api/settings/embedding-models/switch` | Switch model + background reindex |
| POST | `/api/index` | Trigger indexing |
| POST | `/api/index/cancel` | Cancel running index |
| GET | `/api/index/events` | SSE stream of real-time index events (file indexed/deleted/error) |

## Export

Requires the `export` feature flag. Plugin: `app/plugins/export/`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/export` | Export conversations as markdown or JSON |

## Documents (Write API)

Requires the `write_api` feature flag. Plugin: `app/plugins/write_api/`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/documents` | Create or update a markdown file in a watched source directory |
| DELETE | `/api/documents` | Delete a markdown file from a watched source directory |

### POST /api/documents

```json
{
  "path": "notes/idea.md",
  "content": "# My Idea\n\nContent here...",
  "source": "",
  "overwrite": false
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `path` | (required) | Relative path within the source directory (must end in `.md`) |
| `content` | (required) | Markdown content to write |
| `source` | first configured source | Target source directory (must be a configured source) |
| `overwrite` | `false` | Allow overwriting existing files (409 if file exists and `false`) |

### DELETE /api/documents

Query parameters: `path` (required), `source` (optional, defaults to first source).

### Error codes

| Code | Cause |
|------|-------|
| **403** | Target source has `writable: false` — writes are not allowed to read-only sources |
| **409** | File already exists and `overwrite` is `false` |
| **422** | Validation error, or the target directory does not exist / is not writable on disk |

## Planner

Requires `plugins.planner.enabled: true`. Plugin: `app/plugins/planner/`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/planner/plan` | Generate an implementation plan using MCTS |
| POST | `/api/planner/plan/stream` | Stream plan generation progress as SSE |
| GET | `/api/planner/plans` | List saved plans |
| POST | `/api/planner/plans` | Save a plan |
| GET | `/api/planner/plans/{id}` | Load a saved plan |
| DELETE | `/api/planner/plans/{id}` | Delete a saved plan |
| GET | `/api/planner/skills` | List available agent skills |

## Doc Map

Requires `plugins.docmap.enabled: true`. Plugin: `app/plugins/docmap/`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/docmap/data` | Compute document similarity map (nodes, edges, clusters, word clouds) |
| GET | `/api/docmap/stats` | Doc map statistics (doc count, chunk count) |
| GET | `/api/docmap/status` | Check if cached data is available (no computation) |
| GET | `/api/docmap/edge-detail` | Chunk-level similarity detail for a document pair |
| GET | `/api/docmap/progress` | Current computation progress |

Accepts optional `scope_ids`, `ad_hoc_tags[]`, `word_clouds`, `min_weight`, `bucket_id`, `bucket_min_weight`, and `client_threshold` query parameters. Supports both scope and tag filtering. Filters out files with `include_rag=false`.

When `bucket_id` is set, the response includes the bucket's documents merged into the graph with `_bucket: true` markers and the bucket's color. Bucket nodes always render even if they have no surviving edges — selecting a bucket should never make it invisible.

**Cross-collection edges** (bucket ↔ scope) are computed via Reciprocal Rank Fusion of four similarity signals — mean top-K chunk-pair cosine, max chunk-pair cosine, document-level TF-IDF cosine, and relative neighbour rank — rather than a single cosine threshold. Fused scores are normalized per bucket doc to [0, 1], and `bucket_min_weight` (default 0.50) filters edges by this normalized score: 1.0 keeps only each bucket doc's single best match, 0.0 keeps every computed connection. See [docmap.md](../explanation/docmap.md#bucket-overlay) for the full explanation.

`client_threshold` is metadata only: the frontend passes its current Similarity-slider value so the backend debug log (`{data_directory}/docmap-debug.log`) can record slider state alongside each build. It does not affect the response.

## Knowledge Graph

Requires `plugins.knowledge_graph.enabled: true`. Plugin: `app/plugins/knowledge_graph/`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/knowledge-graph/data` | All entities and relationships (accepts `entity_types`, `rel_types` filters) |
| GET | `/api/knowledge-graph/entity` | Single entity with all connections (`?name=X`) |
| GET | `/api/knowledge-graph/path` | BFS shortest path (`?source=X&target=Y&max_hops=6`) |
| GET | `/api/knowledge-graph/stats` | Entity/relationship counts |
| GET | `/api/knowledge-graph/file-entity-counts` | Entity count per file |
| POST | `/api/knowledge-graph/extract` | Start background entity extraction |
| GET | `/api/knowledge-graph/extract/status` | Extraction progress |
| POST | `/api/knowledge-graph/extract/cancel` | Cancel running extraction |
| POST | `/api/knowledge-graph/extract-file` | Extract entities from a single file (`?path=X`) |
| POST | `/api/knowledge-graph/clear` | Clear all KG data |

### Ollama Model Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings/ollama/status` | Check Ollama reachability and get starter model suggestions |
| POST | `/api/settings/ollama/pull` | Pull a model from Ollama (SSE progress streaming) |

## File Converter

Requires `plugins.converter.enabled: true`. Plugin: `app/plugins/converter/`. Requires Pandoc installed on the system.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/converter/formats` | List supported formats and check tool availability |
| POST | `/api/converter/convert` | Start batch conversion (source_dir, dest_dir, optional format filter) |
| GET | `/api/converter/status` | Conversion progress (running, files done/total, errors) |
| POST | `/api/converter/cancel` | Cancel running conversion |

## Tags

Requires the `tags` feature flag. Plugin: `app/plugins/tags/`.

Tag CRUD, folder-based auto-tagging, and optional AI generation. Tags are stored in a plugin-owned database (`data/tags.db`).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tags` | List unique tags (paginated) |
| PUT | `/api/files/tags` | Update tags on a file (`{ path, tags[] }`) |
| PUT | `/api/files/bulk-tags` | Bulk update tags on multiple files (add/remove/replace) |
| POST | `/api/files/auto-tag-preview` | Preview auto-tag assignments by folder pattern (dry run) |
| POST | `/api/files/auto-tag-apply` | Apply auto-tag assignments from preview |

### AI Tag Generation

These endpoints additionally require the `mcp_tag_generator` feature flag (sub-flag).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/tags/generate` | Generate AI tags for a markdown file |
| POST | `/api/tags/apply` | Apply tags to a file's frontmatter |
| POST | `/api/tags/bulk` | Bulk-tag files in a directory |

## Buckets

Requires `plugins.buckets.enabled: true`. Plugin: `app/plugins/buckets/`.

Temporary scoped document collections with independent vector storage. Each bucket gets its own ChromaDB collection for isolated search and RAG chat. Expired buckets are automatically cleaned up on startup.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/buckets` | List all buckets with metadata |
| POST | `/api/buckets` | Create a new bucket from source paths |
| GET | `/api/buckets/{id}` | Get bucket details |
| DELETE | `/api/buckets/{id}` | Delete a bucket and its vector data |
| POST | `/api/buckets/{id}/search` | Search within a bucket |
| POST | `/api/buckets/{id}/chat` | RAG chat scoped to a bucket |
| POST | `/api/buckets/{id}/add` | Add documents to an existing bucket (skips duplicates) |
| POST | `/api/buckets/{id}/documents` | Push documents by content (no filesystem access needed) |
| GET | `/api/buckets/{id}/file` | Read full content of a bucket file (reconstructed from chunks). Query param: `path`. |

### POST /api/buckets

```json
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
| `name` | (required) | Unique bucket name |
| `sources` | `[]` | List of `{path, glob}` source descriptors (optional — omit to create an empty bucket) |
| `expires_in` | null | Optional auto-delete after this many seconds (min 60) |
