# AI Tag Generation

Use LLM-powered analysis to automatically suggest and apply tags to your markdown files. The AI reads each document, considers similar documents in your knowledge base for consistency, and suggests 3-7 relevant tags.

Requires the `tags` plugin with `ai_generation` enabled, and a configured LLM provider.

## Setup

Enable in `config/settings.yaml`:

```yaml
plugins:
  tags:
    enabled: true
    ai_generation: true
```

Restart the server to activate.

## How It Works

1. **Read the file** — parses frontmatter and content
2. **Find similar documents** — retrieves related docs from the knowledge base via RAG
3. **LLM analysis** — the model analyzes content, considers existing tags and tags from similar documents for consistency
4. **Format and validate** — lowercase hyphenated format, deduplicated, sorted, typically 3-7 tags

Tags from similar documents are included in the prompt so the LLM produces consistent tagging across your knowledge base — if similar docs use "architecture" and "infrastructure", the new doc gets the same tags rather than inventing synonyms.

## Generate Tags (Preview)

Preview suggested tags without modifying the file:

```bash
curl -X POST http://localhost:9713/api/tags/generate \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/your/document.md",
    "use_similar_docs": true,
    "auto_apply": false
  }'
```

Response:
```json
{
  "status": "success",
  "suggested_tags": ["python", "web-development", "fastapi", "tutorial"],
  "existing_tags": ["python"],
  "similar_tags": ["python", "backend", "api"],
  "preview": "=== FRONTMATTER PREVIEW ===\n...",
  "applied": false
}
```

## Generate and Apply

Apply tags directly (creates a backup first):

```bash
curl -X POST http://localhost:9713/api/tags/generate \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/your/document.md",
    "auto_apply": true
  }'
```

A timestamped backup is created before any modification:
```
document.md                          # Modified with new tags
document.20260206_153045.backup.md   # Backup of original
```

## Apply Specific Tags

Skip AI generation and apply tags you've already decided on:

```bash
curl -X POST http://localhost:9713/api/tags/apply \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/your/document.md",
    "tags": ["python", "tutorial", "advanced"],
    "merge_with_existing": true
  }'
```

## Bulk Tag a Directory

Tag multiple files at once:

```bash
curl -X POST http://localhost:9713/api/tags/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "directory": "/path/to/docs",
    "pattern": "*.md",
    "auto_apply": false,
    "max_files": 20
  }'
```

## Manual Tagging

You can also add tags manually:

- **From the UI:** Open a file in the file viewer, click Edit, modify the tags, and save
- **From frontmatter:** Add a `tags:` section to your markdown file's YAML frontmatter:

```yaml
---
title: My Document
tags:
  - architecture
  - decisions
  - infrastructure
---
```

Tags are extracted from frontmatter during indexing and stored in the TagDB for filtering.

- **From the API:** `PUT /api/files/tags` with `{"path": "...", "tags": ["tag1", "tag2"]}`

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `403: AI tag generation is disabled` | Set `plugins.tags.ai_generation: true` in settings and restart |
| Tags not appearing in sidebar | Tags are synced from ChromaDB on startup — restart the server |
| LLM not responding | Check provider config in Settings > Chat Model |
