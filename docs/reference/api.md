# API Reference

All endpoints under `http://localhost:9713/api/v1/`. Interactive docs (Swagger UI) at `http://localhost:9713/docs`.

## Authentication

When an API key is configured (via Docker secret `markdownkb_api_key` or `MARKDOWNKB_API_KEY` env var), all `/api/v1/*` endpoints require the header:

```
X-MarkdownKB-Key: <your-key>
```

Missing or invalid keys return **401 Unauthorized**. `/api/v1/health` is always public (no key required). When no key is configured, authentication is disabled.

## Health & Stats

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/health/llm` | Lightweight LLM health check (for status polling) |
| GET | `/api/v1/stats` | Index statistics (files, chunks, embedding model, provider) |

## Search

Requires the `search` feature flag. Plugin: `app/plugins/search/`.

Supports Google-style quoted phrases: `"exact phrase"` requires literal match in chunk content. Unquoted terms use semantic (vector) search. Configurable via `plugins.search` in settings.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/search` | Semantic search with optional query enhancement. Pass `bucket_id` to search within a specific bucket. |
| GET | `/api/v1/searches` | List search history (paginated) |
| GET | `/api/v1/searches/{id}/load` | Load historical search version with preserved results |
| GET | `/api/v1/searches/{id}/versions` | Get all versions of a search (original + re-queries) |
| GET | `/api/v1/searches/{id}/compare` | Compare historical search against current KB state |
| DELETE | `/api/v1/searches/{id}` | Delete a search from history |
| POST | `/api/v1/search/summarize` | AI summary of search results (streaming). Pass `deep_research: true` for MCTS-powered multi-angle synthesis (requires `deep_research` feature flag). |
| POST | `/api/v1/search/enhance-query` | LLM query enhancement (keywords, acronyms) |

## Chat

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat` | RAG chat (non-streaming) |
| POST | `/api/v1/chat/stream` | SSE streaming chat. Pass `bucket_id` to chat within a specific bucket. |
| DELETE | `/api/v1/chat/history` | Clear conversation |
| POST | `/api/v1/chat/save-plan` | Save response as markdown |

## Threads

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/threads` | List chat threads (paginated) |
| GET | `/api/v1/threads/{id}/messages` | Get messages for a thread |
| DELETE | `/api/v1/threads/{id}` | Delete a thread |
| PATCH | `/api/v1/threads/{id}` | Rename a thread |

## Files

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/files` | List all indexed files with status, chunk count, and tags. Accepts `limit`/`offset` for pagination. Response key is `items`. |
| GET | `/api/v1/file` | Read full content of a file by `?path=`. Accepts filesystem paths (must be under a configured source root) and `bucket://name/file.md` virtual paths (reconstructed from ChromaDB). Returns 403 for other paths. |
| GET | `/api/v1/file/status` | Get indexing status of a single file by `?path=`. Returns synthetic `status: complete` for `bucket://` virtual paths (not tracked in the indexing DB). |
| GET | `/api/v1/folders` | List unique folders from indexed documents |
| PUT | `/api/v1/files/include` | Toggle index inclusion for a file — turning off deletes existing chunks and excludes the file from future indexing |
| POST | `/api/v1/files/search` | Content-based file search (returns file paths). Supports quoted exact phrases. |
| POST | `/api/v1/files/index` | Index a single file — parse, embed, store. File must be within a configured source directory. |
| PUT | `/api/v1/files/index` | Re-embed a file's existing chunks (use after changing embedding model). |
| DELETE | `/api/v1/files/index` | **Unindex a single file** — removes chunks from the vector store without touching the file on disk. Body: `{"path": "...", "purge": false}`. With `purge: false` (default): resets status to `pending`, keeps the tracking row so the file can be re-indexed later. With `purge: true`: deletes the tracking row entirely — the file disappears from the Files tab and won't be re-indexed on next scan (use this when the file is in `global_ignore` or you want to forget it completely). Returns `{"status": "unindexed"|"purged", "chunks_removed": N}`. |
| DELETE | `/api/v1/sources/index` | Unindex all files under a source directory (bulk version of the above) |
| DELETE | `/api/v1/files/orphaned` | Prune tracker rows for files that no longer exist on disk |

## Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/settings` | Get full settings |
| GET | `/api/v1/settings/status` | Returns `{"dirty": bool}` — true if `settings.yaml` has been modified on disk since it was last loaded. Polled by the UI to show the "Apply Updates" button. |
| POST | `/api/v1/settings/reload` | Re-read `settings.yaml` from disk and apply to the live instance. Called on Settings page mount and when the user clicks "Apply Updates". |
| GET | `/api/v1/sources` | List source directories |
| POST | `/api/v1/sources` | Add source directory (immediately starts watching + indexing) |
| DELETE | `/api/v1/sources` | Remove source directory (with optional `cleanup` to unindex files) |
| POST | `/api/v1/ignore-patterns` | Add a `global_ignore` glob pattern. Body: `{"pattern": "**/code_reviews/**"}`. Files matching it are skipped on the **next** scan — does not remove already-indexed files (use `DELETE /api/v1/files/stale-ignored` to purge them). |
| DELETE | `/api/v1/ignore-patterns` | Remove a `global_ignore` glob pattern. Body: `{"pattern": "..."}` |
| GET | `/api/v1/files/stale-ignored` | Return indexed files whose paths now match the active `global_ignore` patterns. Returns `{"count": N, "paths": [...]}`. Count > 0 means chunks exist in the vector store for files the scanner now ignores. |
| DELETE | `/api/v1/files/stale-ignored` | Purge chunks and tracking records for all files matching active `global_ignore` patterns. Safe to call at any time — only removes files that are both indexed and ignored. Returns `{"status": "ok", "purged": N, "paths": [...]}`. |
| GET | `/api/v1/project-roots` | List project root configurations |
| POST | `/api/v1/project-roots` | Add project root (path, include/exclude patterns, optional title) |
| PUT | `/api/v1/project-roots` | Update project root patterns and optional title |
| DELETE | `/api/v1/project-roots` | Remove project root (with optional `cleanup` to unindex) |
| PUT | `/api/v1/settings/provider` | Save LLM provider config (name, model, api_base, api_key) |
| PUT | `/api/v1/settings/llm-params` | Save generation parameters (temperature, max_tokens, num_ctx) |
| POST | `/api/v1/settings/test-connection` | Test LLM connectivity |
| POST | `/api/v1/settings/ping-model` | Ping a specific model |
| POST | `/api/v1/settings/refresh-models` | Fetch model list from provider |
| POST | `/api/v1/settings/test-prompt` | Test a prompt with the LLM (streaming) |
| POST | `/api/v1/settings/model-info` | Get model details |
| PUT | `/api/v1/settings/features` | Toggle feature flag |
| PUT | `/api/v1/settings/system-prompt` | Update system prompt |
| PUT | `/api/v1/settings/intelligent-search` | Toggle intelligent search |
| PUT | `/api/v1/settings/search-summary-prompt` | Update search summary prompt |
| PUT | `/api/v1/settings/retrieval` | Update retrieval settings |
| GET | `/api/v1/settings/plugins/{name}` | Get plugin configuration |
| PUT | `/api/v1/settings/plugins/{name}` | Update plugin configuration (shallow merge) |
| GET | `/api/v1/settings/log-level` | Get current log level |
| PUT | `/api/v1/settings/log-level` | Set log level (`INFO`, `DEBUG`, or `OFF`) |
| GET | `/api/v1/settings/logs` | Get log entries (incremental via `?since=`) |
| DELETE | `/api/v1/settings/logs` | Clear log buffer |
| GET | `/api/v1/settings/presets` | List retrieval presets |
| POST | `/api/v1/settings/presets` | Create preset (name + settings, or snapshot current) |
| PUT | `/api/v1/settings/presets/{id}` | Update preset name/settings |
| DELETE | `/api/v1/settings/presets/{id}` | Delete preset |
| POST | `/api/v1/settings/presets/{id}/load` | Apply preset to active retrieval config |

## Plugin Management

Core router (always registered). Manages plugin discovery, installation, and removal.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/plugins` | List all plugins (builtin + external) with manifests, plus core feature flags |
| GET | `/api/v1/plugins/{name}` | Get details for a specific plugin |
| POST | `/api/v1/plugins/install` | Install plugin from GitHub URL (`{ url }`) |
| DELETE | `/api/v1/plugins/{name}` | Uninstall an external plugin (builtin plugins cannot be removed) |

### GET /api/v1/plugins response

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
      "name": "file_watcher",
      "display_name": "File Watcher",
      "enabled": true,
      "category": "core"
    }
  ]
}
```

### POST /api/v1/plugins/install

Accepts GitHub URLs in several formats:
- `https://github.com/user/repo`
- `https://github.com/user/repo/tree/main/path/to/plugin`
- `user/repo`

The plugin must contain `__init__.py` with `FEATURE_FLAG` and `router` exports. A `plugin.yaml` manifest is recommended. If `requirements.txt` is present, dependencies are installed automatically.

## MCP Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/settings/mcp` | Get all MCP tool configurations |
| GET | `/api/v1/settings/mcp/{tool}` | Get config for a specific MCP tool |
| PATCH | `/api/v1/settings/mcp` | Update MCP tool configuration |

## Database Maintenance

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/settings/database-stats` | Stats for all databases |
| POST | `/api/v1/settings/database/clear-chats` | Clear chat history |
| POST | `/api/v1/settings/database/clear-searches` | Clear search history |
| POST | `/api/v1/settings/database/clear-vectors` | Clear vector DB and file tracking |
| POST | `/api/v1/settings/database/compact-chats` | Compact chat database |
| POST | `/api/v1/settings/database/compact-searches` | Compact search database |
| GET | `/api/v1/settings/database/maintenance-preview` | Scan for orphaned chunks, segment dirs, and VACUUM estimate |
| POST | `/api/v1/settings/database/cleanup-orphans` | Delete ChromaDB chunks whose source files no longer exist |
| POST | `/api/v1/settings/database/compact-vectors` | Delete orphaned HNSW segment dirs and VACUUM chroma.sqlite3 |

## Scopes

Named subsets of your knowledge base. Scopes can filter by folders, tags, or both. Pass a scope to Search, Chat, and Planner to restrict retrieval.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/scopes` | List all scopes |
| POST | `/api/v1/scopes` | Create a scope (`{ name, folders[], tags[] }`) |
| GET | `/api/v1/scopes/{id}` | Get a scope by ID |
| PUT | `/api/v1/scopes/{id}` | Update a scope (`{ name, folders[], tags[] }`) |
| DELETE | `/api/v1/scopes/{id}` | Delete a scope |

A scope requires at least one folder or tag. When resolved, folder filtering restricts by source path prefix; tag filtering uses OR logic (documents matching any listed tag are included). Both can be combined.

Search, Chat, and Planner endpoints accept an optional `scope_id` field in their request bodies. When provided, retrieval is restricted to the scope's folders and/or tags.

MCP tools (`search`, `search_documents`, `chat`, `plan`, `deep_research`) also accept a `scope_id` parameter for the same behavior. Use the `list_scopes` MCP tool to discover available scopes. See [MCP Server](mcp-server.md#scope-support) for details.

## Background Tasks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/tasks` | List recent background tasks (newest first). Query: `kind`, `limit` (max 200) |
| GET | `/api/v1/tasks/{task_id}` | Get status of a single background task |

Task statuses: `pending` → `running` → `succeeded` / `failed`. Failed tasks include an `error` field. Task kinds include `startup_index`, `source_index`, and `watcher_rescan_index`.

## Embeddings & Indexing

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/settings/embedding-models` | List embedding models + install status |
| GET | `/api/v1/settings/embedding-models/status` | Poll background reindex progress |
| POST | `/api/v1/settings/embedding-models/install` | Download an embedding model |
| PUT | `/api/v1/settings/embedding-models/switch` | Switch model + background reindex |
| POST | `/api/v1/index` | Trigger indexing |
| POST | `/api/v1/index/cancel` | Cancel running index |
| GET | `/api/v1/index/events` | SSE stream of real-time index events (file indexed/deleted/error) |

## Export

Requires the `export` feature flag. Plugin: `app/plugins/export/`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/export` | Export conversations as markdown or JSON |

## Markdown Export

Core endpoints (always available). Return downloads, not JSON.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/export/markdown` | Download a `.zip` of all indexed `.md` files — sources, bucket documents (reconstructed from ChromaDB), and wiki_compile output |
| GET | `/api/v1/export/snapshot` | Download a full snapshot `.tar.gz` — databases, ChromaDB, config, plus a `markdown/` subtree (same as the archive above). Equivalent to `POST /api/v1/backups/create` with `include_markdown: true`. |

## Backups

Core endpoints (always available). Return downloads or accept uploads.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/backups/status` | Restart-pending state, data-dir size, running version |
| POST | `/api/v1/backups/create` | Build and stream a `.tar.gz` backup (`include_config`, `include_sources`, `include_chromadb` flags) |
| POST | `/api/v1/backups/preview` | Read the manifest from an uploaded archive without applying it (multipart file upload) |
| POST | `/api/v1/backups/restore` | Apply an uploaded backup; writes a restart-required marker on success |
| DELETE | `/api/v1/backups/restart-marker` | Acknowledge a completed restore and clear the restart banner |

## Documents (Write API)

Requires the `write_api` feature flag. Plugin: `app/plugins/write_api/`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/documents` | Create or update a markdown file in a watched source directory |
| DELETE | `/api/v1/documents` | Delete a markdown file from a watched source directory |

### POST /api/v1/documents

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

### DELETE /api/v1/documents

Query parameters: `path` (required), `source` (optional, defaults to first source).

### Error codes

| Code | Cause |
|------|-------|
| **403** | Target source has `writable: false` — writes are not allowed to read-only sources |
| **409** | File already exists and `overwrite` is `false` |
| **422** | Validation error, or the target directory does not exist / is not writable on disk |

Every successful write/delete returns a `version_commit` field: the SHA of the auto-commit created in the per-source managed git repo, or `null` when the source has `versioned: false` or versioning is globally disabled.

## Versioning

Git-backed revision history for writable sources. Enabled by default; controlled by `versioning.enabled` and the per-source `versioned` flag (see [Configuration: Versioning](configuration.md#versioning)).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/versioning/history?path={abs}&limit={n}` | List commits that touched a file (newest first) |
| GET | `/api/v1/versioning/diff?path={abs}&commit={sha}` | Unified diff of a file between a commit and its parent |
| GET | `/api/v1/versioning/content?path={abs}&commit={sha}` | File contents at a specific commit (for side-by-side views) |
| POST | `/api/v1/versioning/restore` | Write a past revision back to disk as a new commit |

Restore request body:

```json
{ "path": "/abs/path/to/file.md", "commit": "a1b2c3d4..." }
```

All endpoints require the file to be under a source with `versioned: true`. Returns **404** for unversioned or unknown paths, **503** when versioning is disabled.

## Planner

Requires `plugins.planner.enabled: true`. Plugin: `app/plugins/planner/`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/planner/plan` | Generate an implementation plan using MCTS |
| POST | `/api/v1/planner/plan/stream` | Stream plan generation progress as SSE |
| GET | `/api/v1/planner/plans` | List saved plans |
| POST | `/api/v1/planner/plans` | Save a plan |
| GET | `/api/v1/planner/plans/{id}` | Load a saved plan |
| DELETE | `/api/v1/planner/plans/{id}` | Delete a saved plan |
| GET | `/api/v1/planner/skills` | List available agent skills |

## Doc Map

Requires `plugins.docmap.enabled: true`. Plugin: `app/plugins/docmap/`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/docmap/data` | Compute document similarity map (nodes, edges, clusters, word clouds) |
| GET | `/api/v1/docmap/stats` | Doc map statistics (doc count, chunk count) |
| GET | `/api/v1/docmap/status` | Check if cached data is available (no computation) |
| GET | `/api/v1/docmap/edge-detail` | Chunk-level similarity detail for a document pair. Accepts `bucket_id` when either side is a bucket doc. |
| GET | `/api/v1/docmap/edge-explain` | LLM-generated one-sentence explanation of why two docs are connected. Accepts `bucket_id` (for bucket cross-edges) and `refresh=true` (bypass cache). |
| GET | `/api/v1/docmap/progress` | Current computation progress |

Accepts optional `scope_ids`, `ad_hoc_tags[]`, `word_clouds`, `min_weight`, `bucket_ids`, `bucket_min_weight`, and `client_threshold` query parameters. Supports both scope and tag filtering. Filters out files with `include_in_index=false`.

When `bucket_ids` is set (comma-separated bucket IDs or names), the response includes each bucket's documents merged into the graph with `_bucket: true` markers and the bucket's color. Bucket nodes always render even if they have no surviving edges — selecting a bucket should never make it invisible. The legacy `bucket_id` (single) parameter is still accepted for backwards compatibility.

**Cross-collection edges** (bucket ↔ scope) are computed via Reciprocal Rank Fusion of four similarity signals — mean top-K chunk-pair cosine, max chunk-pair cosine, document-level TF-IDF cosine, and relative neighbour rank — rather than a single cosine threshold. Fused scores are normalized per bucket doc to [0, 1], and `bucket_min_weight` (default 0.50) filters edges by this normalized score: 1.0 keeps only each bucket doc's single best match, 0.0 keeps every computed connection. See [docmap.md](../explanation/docmap.md#bucket-overlay) for the full explanation.

`client_threshold` is metadata only: the frontend passes its current Similarity-slider value so the backend debug log (`{data_directory}/docmap-debug.log`) can record slider state alongside each build. It does not affect the response.

## Knowledge Graph

Requires `plugins.knowledge_graph.enabled: true`. Plugin: `app/plugins/knowledge_graph/`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/knowledge-graph/data` | All entities and relationships (accepts `entity_types`, `rel_types` filters) |
| GET | `/api/v1/knowledge-graph/entity` | Single entity with all connections (`?name=X`) |
| GET | `/api/v1/knowledge-graph/path` | BFS shortest path (`?source=X&target=Y&max_hops=6`) |
| GET | `/api/v1/knowledge-graph/stats` | Entity/relationship counts |
| GET | `/api/v1/knowledge-graph/file-entity-counts` | Entity count per file |
| POST | `/api/v1/knowledge-graph/extract` | Start background entity extraction |
| GET | `/api/v1/knowledge-graph/extract/status` | Extraction progress |
| POST | `/api/v1/knowledge-graph/extract/cancel` | Cancel running extraction |
| POST | `/api/v1/knowledge-graph/extract-file` | Extract entities from a single file (`?path=X`) |
| POST | `/api/v1/knowledge-graph/clear` | Clear all KG data |

### Ollama Model Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/settings/ollama/status` | Check Ollama reachability and get starter model suggestions |
| POST | `/api/v1/settings/ollama/pull` | Pull a model from Ollama (SSE progress streaming) |

## File Converter

Requires `plugins.converter.enabled: true`. Plugin: `app/plugins/converter/`. Uses Microsoft markitdown (pure Python — no external tools required).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/converter/url` | Fetch a URL and convert to markdown (web pages, YouTube, etc.) |
| POST | `/api/v1/converter/upload` | Upload a file and convert to markdown (returns markdown, does not write to KB) |
| POST | `/api/v1/converter/ingest` | Upload a file, convert, and import it directly into the main knowledge base |
| GET | `/api/v1/converter/formats` | List supported input formats |
| POST | `/api/v1/converter/convert` | Start batch conversion (source_dir → dest_dir) |
| GET | `/api/v1/converter/status` | Conversion progress (running, files done/total, errors) |
| POST | `/api/v1/converter/cancel` | Cancel running conversion |

### POST /api/v1/converter/url

Request: `{ "url": "https://..." }`

Response:

```json
{
  "markdown": "**Source:** https://...\n\n# Page Title\n...",
  "title": "Page Title",
  "transcript_support": true
}
```

- `title` — extracted page or video title (empty string if unavailable)
- `transcript_support` — whether `youtube_transcript_api` is installed (YouTube transcripts require the `full` image variant)
- Source URL is prepended as `**Source:** <url>` if not already present in the content

### POST /api/v1/converter/upload

Request: multipart form with a `file` field.

Response:

```json
{
  "markdown": "# Converted content...",
  "filename": "original-filename.pdf"
}
```

Supported formats: PDF, Word (docx), PowerPoint (pptx), Excel (xlsx/xls), HTML, EPUB, CSV, plain text, reStructuredText, RTF, LibreOffice (odt), Jupyter notebooks (ipynb), Outlook messages (msg).

## Tags

Requires the `tags` feature flag. Plugin: `app/plugins/tags/`.

Tag CRUD, folder-based auto-tagging, and optional AI generation. Tags are stored in a plugin-owned database (`data/tags.db`).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/tags` | List unique tags (paginated) |
| PUT | `/api/v1/files/tags` | Update tags on a file (`{ path, tags[] }`) |
| PUT | `/api/v1/files/bulk-tags` | Bulk update tags on multiple files (add/remove/replace) |
| POST | `/api/v1/files/auto-tag-preview` | Preview auto-tag assignments by folder pattern (dry run) |
| POST | `/api/v1/files/auto-tag-apply` | Apply auto-tag assignments from preview |

### AI Tag Generation

These endpoints additionally require the `mcp_tag_generator` feature flag (sub-flag).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/tags/generate` | Generate AI tags for a markdown file |
| POST | `/api/v1/tags/apply` | Apply tags to a file's frontmatter |
| POST | `/api/v1/tags/bulk` | Bulk-tag files in a directory |

## Wiki Compile

Requires `plugins.wiki_compile.enabled: true`. Plugin: `app/plugins/wiki_compile/`.

Karpathy-style wiki compilation — reads a source document, asks the configured LLM to produce a summary page, and writes it into a managed wiki directory while maintaining `index.md` and `log.md` for navigation. See [wiki-compile.md](../explanation/wiki-compile.md) and `app/plugins/wiki_compile/README.md` for the architectural pattern.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/wiki-compile/wikis` | List managed wikis (name, path, page count, last ingest date) |
| POST | `/api/v1/wiki-compile/wikis` | Create a managed wiki — auto-registers as a writable source, auto-mounts in Docker |
| DELETE | `/api/v1/wiki-compile/wikis/{name}` | Deregister a wiki (directory itself is preserved on disk) |
| POST | `/api/v1/wiki-compile/ingest` | Ingest one source file into a wiki by name |

Create a wiki:

```json
{ "name": "research" }
```

Optionally pass `path` to override the default location (`{data_directory}/wikis/{name}/`). The response includes `docker_restart_required: true` when a custom path outside the project/data directory was added — the new bind mount only takes effect after `make docker-down && make docker-up`.

Ingest into a wiki:

```json
{
  "source_path": "/absolute/path/to/source.md",
  "wiki": "research",
  "force": false
}
```

`force=true` overwrites an existing summary for the same source. Uses `app.rag.llm.get_completion` — same LLM plumbing as search summarize and edge explain. Response includes `existing_pages_used` listing related pages from the target wiki that were passed as context to the LLM (empty array when the wiki is empty or the indexer hasn't yet picked up new pages).

## Buckets

Requires `plugins.buckets.enabled: true`. Plugin: `app/plugins/buckets/`.

Temporary scoped document collections with independent vector storage. Each bucket gets its own ChromaDB collection for isolated search and RAG chat. Expired buckets are flagged on startup but not deleted — they remain visible until manually removed.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/buckets` | List all buckets with metadata |
| POST | `/api/v1/buckets` | Create a new bucket from source paths |
| GET | `/api/v1/buckets/{id}` | Get bucket details |
| PATCH | `/api/v1/buckets/{id}` | Update bucket metadata. Accepts any subset of: `name`, `expires_in`, `color`, `description`, `scope_paths`. `scope_paths` is a list of file paths to restrict retrieval to (null = all files). |
| DELETE | `/api/v1/buckets/{id}` | Delete a bucket and its vector data |
| POST | `/api/v1/buckets/{id}/search` | Search within a bucket. Returns 410 if the bucket is expired. |
| POST | `/api/v1/buckets/{id}/chat` | RAG chat scoped to a bucket. Returns 410 if the bucket is expired. |
| POST | `/api/v1/buckets/{id}/add` | Add documents to an existing bucket (skips duplicates) |
| POST | `/api/v1/buckets/{id}/documents` | Push documents by content (no filesystem access needed) |
| PATCH | `/api/v1/buckets/{id}/documents` | Rename a virtual document. Body: `{ old_path, new_name }`. Only `bucket://` paths accepted; returns 400 for filesystem-sourced files. |
| GET | `/api/v1/buckets/{id}/files` | List all files in a bucket. Response: `{ files: [{ path, title, chunk_count, indexed_at }], indexing }`. `indexed_at` is an ISO-like UTC timestamp string or null for files ingested before this field was added. |
| GET | `/api/v1/buckets/{id}/file` | Read full content of a bucket file (reconstructed from chunks). Query param: `path`. |
| GET | `/api/v1/buckets/{id}/export` | Export bucket as a portable zip archive (manifest + pre-computed embeddings) |
| POST | `/api/v1/buckets/import` | Import a bucket from a previously exported zip (multipart file upload, no re-embedding) |
| POST | `/api/v1/buckets/{id}/promote` | Add bucket source paths to the main watched directories in settings |
| GET | `/api/v1/buckets/base-path` | Get the configured base path and whether it is mounted in Docker |
| POST | `/api/v1/buckets/base-path` | Set (or clear) the base path; auto-adds it to Docker mounts if needed |

### POST /api/v1/buckets

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
| `description` | null | Optional free-text description of the bucket's purpose |

## Lint

Requires `plugins.lint.enabled: true`. Plugin: `app/plugins/lint/`.

Tiered knowledge-base health check modelled on Karpathy's Lint verb. Runs four passes over the configured source tiers and writes a flag-only markdown report. Never modifies documents. Works across the whole knowledge base — wiki_compile is not required.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/lint/run` | Run selected passes, persist report, return findings |
| GET | `/api/v1/lint/reports` | List previously generated lint reports sorted newest-first |

### POST /api/v1/lint/run

```json
{
  "passes": ["raw_coverage", "orphan", "within_tier", "cross_tier"],
  "target_wiki": "research"
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `passes` | all four | Subset of passes to run |
| `target_wiki` | `null` | Wiki name to write the report into. When set, report lands in `{wiki_path}/lint/`. When null, uses `{data_dir}/lint-reports/`. |

**Passes:**

| Pass | Type | Description |
|------|------|-------------|
| `raw_coverage` | deterministic | Tier -1 files with no synthesis entry in any wiki's `log.md` |
| `orphan` | deterministic | Tier-1 docs linked by nothing else in the corpus |
| `within_tier` | LLM | Up to 12 pairs of related tier-1 docs checked for contradictions |
| `cross_tier` | LLM | Each tier-1 doc vs its closest tier-0 neighbour: aligned / extension / contradiction / evolution |

Response includes `findings` (array of finding objects with `pass`, `severity`, `kind`, `title`, `detail`, `paths`, `suggested_action`), `counts` by severity, `report_path`, and `report_markdown`. The report is written to disk and picked up by the file watcher — lint findings become retrievable context for future queries.
