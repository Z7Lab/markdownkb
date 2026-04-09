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
curl -X POST http://localhost:9713/api/documents \
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
- **source** — target source directory (empty = first configured source)
- **overwrite** — set `true` to replace an existing file (default `false`, returns 409 if file exists)

### Delete a document

```bash
curl -X DELETE "http://localhost:9713/api/documents?path=notes/meeting-2026-04-09.md"
```

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
- **Overwrite protection** — `save_file` and the REST API refuse to overwrite unless explicitly told to
- **Disabled by default** — both `write_api` and `mcp.save_document` are off out of the box
- **`read_only` gate** — even if `save_document` is true, `mcp.read_only: true` blocks all MCP write tools (save, delete, index)

## Typical workflows

**Agent research capture:** An agent searches the web, summarizes findings, and saves them as markdown. The file is automatically indexed and available for search and chat.

**Webhook ingestion:** A CI pipeline or webhook POSTs converted documents (from Confluence, Notion, etc.) to the write API. MarkdownKB indexes them alongside your local docs.

**Bucket → permanent:** After evaluating temporary bucket content, promote useful docs by saving them to a watched source directory via `save_file`.

## Pushing documents into buckets remotely

Buckets can also be populated by **content push** — sending document content directly over the API without any filesystem access. This is the key use case for remote agents that cannot write files to the MarkdownKB host.

### REST API

```bash
curl -X POST http://localhost:9713/api/buckets/{id}/documents \
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
