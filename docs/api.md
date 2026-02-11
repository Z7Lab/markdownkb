# API Reference

All endpoints under `http://localhost:9713/api/`. Interactive docs (Swagger UI) at `http://localhost:9713/docs`.

## Health & Stats

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/health/llm` | Lightweight LLM health check (for status polling) |
| GET | `/api/stats` | Index statistics (files, chunks, embedding model, provider) |

## Search

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/search` | Semantic search with optional query enhancement |
| GET | `/api/searches` | List search history (paginated) |
| GET | `/api/searches/{id}/load` | Load historical search version with preserved results |
| GET | `/api/searches/{id}/versions` | Get all versions of a search (original + re-queries) |
| GET | `/api/searches/{id}/compare` | Compare historical search against current KB state |
| DELETE | `/api/searches/{id}` | Delete a search from history |
| POST | `/api/search/summarize` | AI summary of search results (streaming) |
| POST | `/api/search/enhance-query` | LLM query enhancement (keywords, acronyms) |
| GET | `/api/folders` | List unique folders from indexed documents |
| GET | `/api/tags` | List unique tags from indexed documents |

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
| PUT | `/api/files/toggle-rag` | Toggle RAG inclusion for a file |
| POST | `/api/files/unindex` | Remove file chunks from index |
| POST | `/api/files/index` | Index a single file |
| POST | `/api/files/reindex` | Re-embed a file's chunks |

## Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings` | Get full settings |
| GET | `/api/sources` | List source directories |
| POST | `/api/sources` | Add source directory |
| DELETE | `/api/sources` | Remove source directory |
| POST | `/api/ignore-patterns` | Add ignore pattern |
| DELETE | `/api/ignore-patterns` | Remove ignore pattern |
| PUT | `/api/settings/provider` | Save LLM provider config |
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

## Embeddings & Indexing

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings/embedding-models` | List embedding models + install status |
| GET | `/api/settings/embedding-models/status` | Poll background reindex progress |
| POST | `/api/settings/embedding-models/install` | Download an embedding model |
| PUT | `/api/settings/embedding-models/switch` | Switch model + background reindex |
| POST | `/api/index` | Trigger indexing |
| POST | `/api/index/cancel` | Cancel running index |

## Export

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/export` | Export conversations as markdown or JSON |

## Tags

Requires the `mcp_tag_generator` feature flag.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/tags/generate` | Generate AI tags for a markdown file |
| POST | `/api/tags/apply` | Apply tags to a file's frontmatter |
| POST | `/api/tags/bulk` | Bulk-tag files in a directory |
