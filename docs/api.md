# API Reference

All endpoints under `http://localhost:9713/api/`. Interactive docs (Swagger UI) at `http://localhost:9713/docs`.

## Authentication

When an API key is configured (via Docker secret `mdkb_api_key` or `MDKB_API_KEY` env var), all `/api/*` endpoints require the header:

```
X-MDKB-Key: <your-key>
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
| POST | `/api/search` | Semantic search with optional query enhancement |
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
| POST | `/api/chat/stream` | SSE streaming chat |
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
| GET | `/api/tags` | List unique tags (merged from vector store and tracking DB) |
| PUT | `/api/files/toggle-rag` | Toggle RAG inclusion for a file |
| PUT | `/api/files/tags` | Update tags on a file (`{ path, tags[] }`) |
| PUT | `/api/files/bulk-tags` | Bulk update tags on multiple files |
| POST | `/api/files/search` | Content-based file search (returns file paths). Supports quoted exact phrases. |
| POST | `/api/files/auto-tag-preview` | Preview auto-tag assignments by folder pattern (dry run) |
| POST | `/api/files/auto-tag-apply` | Apply auto-tag assignments from preview |
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
| PUT | `/api/settings/log-level` | Set log level (INFO/DEBUG) |
| GET | `/api/settings/logs` | Get log entries (incremental via `?since=`) |
| DELETE | `/api/settings/logs` | Clear log buffer |

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

## Planner

Requires the `mcts_planner` feature flag. Plugin: `app/plugins/planner/`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/planner/plan` | Generate an implementation plan using MCTS |
| POST | `/api/planner/plan/stream` | Stream plan generation progress as SSE |
| GET | `/api/planner/plans` | List saved plans |
| POST | `/api/planner/plans` | Save a plan |
| GET | `/api/planner/plans/{id}` | Load a saved plan |
| DELETE | `/api/planner/plans/{id}` | Delete a saved plan |
| GET | `/api/planner/skills` | List available agent skills |

## Knowledge Graph

Requires the `knowledge_graph` feature flag. Plugin: `app/plugins/graph/`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/graph/data` | Compute similarity graph (nodes, edges, clusters, word clouds) |
| GET | `/api/graph/stats` | Graph statistics (doc count, chunk count) |
| GET | `/api/graph/status` | Check if cached graph data is available (no computation) |
| GET | `/api/graph/edge-detail` | Chunk-level similarity detail for a document pair |
| GET | `/api/graph/progress` | Current graph computation progress |

Accepts optional `scope_ids`, `ad_hoc_tags[]`, `word_clouds`, and `min_weight` query parameters. Supports both scope and tag filtering.

## Tags

Requires the `mcp_tag_generator` feature flag. Plugin: `app/plugins/tags/`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/tags/generate` | Generate AI tags for a markdown file |
| POST | `/api/tags/apply` | Apply tags to a file's frontmatter |
| POST | `/api/tags/bulk` | Bulk-tag files in a directory |
