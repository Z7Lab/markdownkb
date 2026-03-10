# Tags Plugin

AI-powered tag generation and application for markdown file frontmatter.

**Feature flag:** `mcp_tag_generator`
**Prefix:** `/api/tags`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/tags/generate` | Generate AI tags for a markdown file |
| POST | `/api/tags/apply` | Apply tags to a file's frontmatter |
| POST | `/api/tags/bulk` | Bulk-tag files in a directory |

## Generate Tags

```json
{
  "file_path": "/path/to/document.md",
  "use_similar_docs": true,
  "auto_apply": false
}
```

When `auto_apply` is false (default), returns a preview of suggested tags without modifying the file. Set to true to write tags directly to the file's frontmatter (with backup).

## Apply Tags

```json
{
  "file_path": "/path/to/document.md",
  "tags": ["kubernetes", "deployment"],
  "merge_with_existing": true,
  "create_backup": true
}
```

## Bulk Tag

```json
{
  "directory": "/path/to/docs",
  "pattern": "*.md",
  "auto_apply": false,
  "max_files": 50
}
```

## Dependencies

- `app.mcp.tag_generator` — LLM-based tag generation and file modification
- `app.rag.retriever` — similar document lookup for context
