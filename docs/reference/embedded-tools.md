# Embedded Tools (Filesystem, Terminal, Tag Generator)

Optional HTTP-based tools that extend mdkb with file browsing, terminal access, and AI tag generation. These are served by the FastAPI app and used internally by the planner for filesystem exploration and skill reviews. Each is controlled by a feature flag in `config/settings.yaml`.

> These are **not** the MCP tools that agents connect to. For the 32 MCP tools (search, chat, buckets, etc.), see [MCP Server](mcp-server.md).

| Tool | Feature Flag | Description |
|------|-------------|-------------|
| Filesystem | `mcp_filesystem` | Browse directories, read files, search by pattern |
| Terminal | `mcp_terminal` | Execute safe shell commands with allowlist |
| Tag Generator | `mcp_tag_generator` | LLM-powered tag suggestions for markdown files |

---

## AI Tag Generation

Uses LLM + RAG to automatically suggest and apply tags to your markdown files.

### Features

- **Safe by default**: Creates backups before modifying files
- **Smart suggestions**: Uses similar documents in your knowledge base for context
- **Preview mode**: See changes before applying
- **Bulk operations**: Tag multiple files at once
- **Merge or replace**: Combine with existing tags or start fresh

### Setup

Enable AI tag generation in `config/settings.yaml`:

```yaml
plugins:
  tags:
    enabled: true
    ai_generation: true
```

The tags plugin must be enabled. The `ai_generation` sub-flag enables the AI generation endpoints within the tags plugin.

Restart the server to activate.

### API Endpoints

#### 1. Generate Tags (Preview)

```bash
curl -X POST http://localhost:9713/api/tags/generate \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/your/document.md",
    "use_similar_docs": true,
    "auto_apply": false
  }'
```

**Response:**
```json
{
  "status": "success",
  "suggested_tags": ["python", "web-development", "fastapi", "tutorial"],
  "existing_tags": ["python"],
  "similar_tags": ["python", "backend", "api"],
  "preview": "=== FRONTMATTER PREVIEW ===\n...",
  "message": "Generated 4 tags for /path/to/your/document.md",
  "applied": false
}
```

#### 2. Generate and Auto-Apply

```bash
curl -X POST http://localhost:9713/api/tags/generate \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/your/document.md",
    "auto_apply": true
  }'
```

**Response includes:**
```json
{
  "applied": true,
  "backup_path": "/path/to/your/document.20260206_153045.backup.md",
  "final_tags": ["python", "web-development", "fastapi", "tutorial"]
}
```

#### 3. Apply Specific Tags

```bash
curl -X POST http://localhost:9713/api/tags/apply \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/your/document.md",
    "tags": ["python", "tutorial", "advanced"],
    "merge_with_existing": true
  }'
```

#### 4. Bulk Tag Directory

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

### Safety Features

#### Backups

Every modification creates a timestamped backup:
```
document.md                          # Original file
document.20260206_153045.backup.md  # Backup
```

#### Restore from Backup

```python
from app.lib.tag_generator.generator import restore_from_backup

restore_from_backup(
    backup_path="/path/to/document.20260206_153045.backup.md",
    original_path="/path/to/document.md"
)
```

#### Preview Mode

By default, `auto_apply=false` shows you a preview:

```
==============================================================
FRONTMATTER PREVIEW
==============================================================

Current tags:
  - python

Proposed tags:
  - python (existing)
  - web-development (NEW)
  - fastapi (NEW)
  - tutorial (NEW)

Other frontmatter (will be preserved):
  title: FastAPI Tutorial
  date: 2026-01-15
==============================================================
```

### How It Works

1. **Read the file** with frontmatter parsing
2. **Extract context**: current tags, all unique tags in knowledge base, tags from similar documents (via RAG)
3. **LLM analysis**: analyzes content, considers title and existing tags, uses similar doc tags for consistency
4. **Format and validate**: lowercase hyphenated format, deduplicated, sorted, typically 3-7 tags

### Integration Examples

#### From Python Code

```python
from app.lib.tag_generator.llm import auto_tag_file_interactive
from app.deps import get_retriever, get_settings

# Generate tags (preview only)
result = auto_tag_file_interactive(
    filepath="/path/to/doc.md",
    retriever=get_retriever(),
    settings=get_settings(),
    auto_apply=False
)

print(result["preview"])
print(f"Suggested: {result['suggested_tags']}")

# Apply if satisfied
if input("Apply? (y/n): ") == "y":
    result = auto_tag_file_interactive(
        filepath="/path/to/doc.md",
        retriever=get_retriever(),
        settings=get_settings(),
        auto_apply=True
    )
    print(f"Backup: {result['backup_path']}")
```

#### Bulk Processing

```python
from app.lib.tag_generator.llm import bulk_tag_directory

results = bulk_tag_directory(
    directory="./docs",
    retriever=get_retriever(),
    settings=get_settings(),
    pattern="*.md",
    auto_apply=False,  # Preview only
    max_files=50
)

for r in results:
    print(f"{r['file']}: {r['suggested_tags']}")
```

### Customization

Edit the prompt in `app/lib/tag_generator/llm.py` to change tag format, count, or style. Add custom validation in `app/lib/tag_generator/generator.py`.

### Troubleshooting

| Problem | Fix |
|---------|-----|
| `403: AI tag generation is disabled` | Set `plugins.tags.enabled: true` and `plugins.tags.ai_generation: true` in `config/settings.yaml` |
| File not found | Use absolute paths or paths relative to the project root |
| LLM not responding | Check provider config, API keys, and `curl http://localhost:9713/api/health` |

---

## Source Code

| Module | Path | Description |
|--------|------|-------------|
| Filesystem handlers | `app/lib/filesystem/handlers.py` | Directory listing, file reading, pattern search |
| Terminal handlers | `app/lib/terminal/handlers.py` | Safe command execution with allowlist |
| Tag generator | `app/lib/tag_generator/generator.py` | Frontmatter parsing, tag application, backups |
| Tag LLM | `app/lib/tag_generator/llm.py` | LLM-powered tag generation, bulk operations |
