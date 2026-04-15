# Writing Documents to MarkdownKB

MarkdownKB can accept new documents from external tools and agents — not just read from watched directories. This enables workflows like capturing meeting notes, saving research, or having agents write findings directly into your knowledge base.

## Two interfaces

| Interface | Use case | Requires |
|-----------|----------|----------|
| **REST API** (`write_api` plugin) | Scripts, webhooks, CI pipelines | `plugins.write_api.enabled: true` |
| **MCP tools** (`save_file`, `delete_file`) | AI agents via MCP | `mcp.save_document: true` + `mcp.read_only: false` |

Both write to the same watched source directories. The file watcher picks up new files automatically and indexes them within seconds.

## Enable write access

### REST API (write_api plugin)

In `config/settings.yaml`:

```yaml
plugins:
  write_api:
    enabled: true
```

Restart the container (`make restart`) to activate.

### MCP tools

In `config/settings.yaml`:

```yaml
mcp:
  read_only: false
  save_document: true
```

Restart the MCP server to activate.

## REST API usage

### Create a document

```bash
curl -X POST http://localhost:9713/api/v1/documents \
  -H "Content-Type: application/json" \
  -d '{
    "path": "notes/meeting-2026-04-09.md",
    "content": "# Meeting Notes\n\nDiscussed the roadmap...",
    "source": "",
    "overwrite": false
  }'
```

- **path** — relative path within the source directory (must end with `.md`)
- **content** — markdown content to write
- **source** — target source directory. Required when multiple source directories are configured (the API returns an error listing available sources). With a single source, defaults to that source.
- **overwrite** — set `true` to replace an existing file (default `false`, returns 409 if file exists)

### Delete a document

```bash
curl -X DELETE "http://localhost:9713/api/v1/documents?path=notes/meeting-2026-04-09.md"
```

The `source` query parameter is also required for `DELETE` when multiple source directories are configured.

## MCP tool usage

### save_file

Creates or updates a markdown file. Agents use this to write research, captures, or generated content.

```
save_file(
  path="captures/anthropic-harness-notes.md",
  content="# Harness Notes\n\nKey findings...",
  source="",
  overwrite=false
)
```

### delete_file

Removes a file from disk, the vector store, and the tracking database.

```
delete_file(path="/home/user/docs/notes/outdated.md")
```

The path must be within a configured source directory. Accepts absolute or relative paths.

## Security

- **Path traversal blocked** — `..` segments and absolute paths (for REST) are rejected
- **Source directory restriction** — files can only be written to or deleted from configured `sources:` directories
- **Per-source writable flag** — each source can be marked `writable: false` to block all writes (REST and MCP). Attempts to write to a read-only source return **403 Forbidden**. The Write API also verifies the directory exists and is writable on disk, returning **422** if not.
- **Overwrite protection** — `save_file` and the REST API refuse to overwrite unless explicitly told to
- **Disabled by default** — both `write_api` and `mcp.save_document` are off out of the box
- **`read_only` gate** — even if `save_document` is true, `mcp.read_only: true` blocks all MCP write tools (save, delete, index)

Sources are configured as dicts with `path` and `writable` fields. When `writable` is omitted it defaults to `true`. The bundled `./docs` directory defaults to `writable: false` in the example config:

```yaml
sources:
  - path: ./docs
    writable: false
  - path: /home/user/docs
    writable: true
```

## Version history

Every write and delete through the Write API or `save_file`/`delete_file` MCP tools is automatically committed to a per-source managed git repo (unless the source has `versioned: false` or `versioning.enabled: false`). The response includes a `version_commit` field with the new commit SHA.

Browse or roll back from the file viewer: open any markdown file, click **History**, select a commit to see the diff, and click **Restore this version** to write it back as a new commit (no history is rewritten).

Or use the API directly:

```bash
# List commits for a file
curl "http://localhost:9713/api/v1/versioning/history?path=/home/user/docs/notes/idea.md"

# View the diff for a specific commit
curl "http://localhost:9713/api/v1/versioning/diff?path=/home/user/docs/notes/idea.md&commit=a1b2c3d4"

# Restore a past revision
curl -X POST http://localhost:9713/api/v1/versioning/restore \
  -H "Content-Type: application/json" \
  -d '{"path":"/home/user/docs/notes/idea.md","commit":"a1b2c3d4"}'
```

For background on why versioning lives inside MarkdownKB and what it covers, see [Versioning](../explanation/versioning.md). For the config surface, see [Configuration: Versioning](../reference/configuration.md#versioning).

## Typical workflows

**Agent research capture:** An agent searches the web, summarizes findings, and saves them as markdown. The file is automatically indexed and available for search and chat.

**Webhook ingestion:** A CI pipeline or webhook POSTs converted documents (from Confluence, Notion, etc.) to the write API. MarkdownKB indexes them alongside your local docs.

**Bucket → permanent:** After evaluating temporary bucket content, promote useful docs by saving them to a watched source directory via `save_file`.

## Pushing documents into buckets remotely

Buckets can also be populated by **content push** — sending document content directly over the API without any filesystem access. This is the key use case for remote agents that cannot write files to the MarkdownKB host.

### REST API

```bash
curl -X POST http://localhost:9713/api/v1/buckets/{id}/documents \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {"name": "vendor-api.md", "content": "# Vendor API\n\nEndpoints..."},
      {"name": "changelog.md", "content": "# Changelog\n\n## v2.0\n\n..."}
    ]
  }'
```

Each document needs a `name` (used as the filename) and `content` (markdown). Documents are stored as vectors in ChromaDB with virtual paths like `bucket://bucket-name/vendor-api.md` — they never touch disk.

### MCP tool

```
bucket_push(bucket: "vendor-docs", documents: [{"name": "api.md", "content": "# API\n\n..."}])
```

This is particularly useful for agents that download or generate content and want to make it searchable without needing filesystem access to the MarkdownKB host.

To read pushed documents back, use `GET /api/v1/buckets/{id}/file?path=...` or the `bucket_read_file` MCP tool. Content is reconstructed from stored chunks.
