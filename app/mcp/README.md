# MCP Tools: AI Tag Generation

## Overview

The **AI Tag Generation** tool uses LLM + RAG to automatically suggest and apply tags to your markdown files.

### Features

✅ **Safe by default**: Creates backups before modifying files
✅ **Smart suggestions**: Uses similar documents in your knowledge base for context
✅ **Preview mode**: See changes before applying
✅ **Bulk operations**: Tag multiple files at once
✅ **Merge or replace**: Combine with existing tags or start fresh

---

## 🔧 Setup

### 1. Enable the feature

Add to your `config/settings.yaml`:

```yaml
features:
  mcp_tag_generator: true  # Add this line
```

### 2. Register the router

In `app/main.py` (or wherever routers are registered), add:

```python
from app.config import get_settings

settings = get_settings()

# Conditionally register tag generation router
if settings.features.get("mcp_tag_generator", False):
    from app.routers import tags
    app.include_router(tags.router)
```

### 3. Restart the server

```bash
./run.sh
```

---

## 📖 Usage

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

---

## 🎯 Use from Chat

You can also use this from the chat interface if you create a skill for it.

### Create a Skill

Create `app/skills/builtin/AUTO_TAG.md`:

```markdown
---
name: auto-tag
description: Generate and apply AI-powered tags to markdown files
---

# Auto Tag Files

Generate intelligent tags for markdown files using AI.

## Usage

Ask me to tag files like:
- "Tag the file docs/tutorial.md"
- "Suggest tags for my Python guides"
- "Auto-tag all files in docs/python/"

## How it works

1. I analyze the file content
2. Check similar documents for context
3. Suggest relevant tags
4. Show you a preview
5. Apply tags with your approval (creates backup)

## Safety

- **Always creates backups** before modifying files
- **Preview mode by default** - you approve before applying
- **Merge mode** - combines with existing tags, doesn't replace
```

---

## 🛡️ Safety Features

### Backups

Every modification creates a timestamped backup:
```
document.md                          # Original file
document.20260206_153045.backup.md  # Backup
```

### Restore from Backup

```python
from app.mcp.tag_generator import restore_from_backup

restore_from_backup(
    backup_path="/path/to/document.20260206_153045.backup.md",
    original_path="/path/to/document.md"
)
```

### Preview Mode

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

---

## 🧠 How It Works

### Tag Generation Algorithm

1. **Read the file** with frontmatter parsing
2. **Extract context**:
   - Current tags (if any)
   - All unique tags in knowledge base
   - Tags from similar documents (via RAG)
3. **LLM analysis**:
   - Analyzes content (first 1000 chars)
   - Considers title and existing tags
   - Uses similar doc tags for consistency
4. **Format and validate**:
   - Lowercase, hyphenated format
   - Deduplicated and sorted
   - 3-7 tags typically

### Example LLM Prompt

```
You are a helpful assistant that generates relevant tags for markdown documents.

Document Title: FastAPI Tutorial
Document Content (excerpt): # Introduction to FastAPI...

Existing tags in knowledge base (for consistency):
python, javascript, web-development, tutorial, api, backend...

Tags from similar documents:
python, fastapi, backend, api

Respond with ONLY a comma-separated list of tags.
```

### Using RAG for Smart Suggestions

The tool queries ChromaDB to find similar documents:

```python
# Get tags from similar docs
results = retriever.search(content[:500], top_k=5)
for result in results:
    doc_tags = result.metadata.get("tags", "")
    # Extract and aggregate tags...
```

This ensures:
- **Consistency** with existing taxonomy
- **Discovery** of related topics
- **Context-aware** suggestions

---

## 🔌 Integration Examples

### From Python Code

```python
from app.mcp.tag_llm import auto_tag_file_interactive
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

### Bulk Processing

```python
from app.mcp.tag_llm import bulk_tag_directory

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

---

## ⚙️ Configuration

### Feature Flag

```yaml
# config/settings.yaml
features:
  mcp_tag_generator: true  # Enable/disable feature
```

### LLM Settings

Uses your existing LLM configuration:

```yaml
llm:
  active_provider: anthropic  # or openai, ollama, etc.
  temperature: 0.3
  max_tokens: 2048
```

---

## 🎨 Customization

### Custom Tag Format

Edit the prompt in `app/mcp/tag_llm.py`:

```python
TAG_GENERATION_PROMPT = """
Your custom instructions here...
Use Title Case tags instead of lowercase
Generate 5-10 tags instead of 3-7
"""
```

### Tag Validation

Add custom validation in `tag_generator.py`:

```python
def format_tags_for_frontmatter(tags: list[str]) -> list[str]:
    # Add your custom rules
    normalized = []
    for tag in tags:
        # Custom validation/transformation
        if len(tag) < 2:  # Skip too-short tags
            continue
        if tag in BLACKLIST:  # Skip blacklisted tags
            continue
        normalized.append(tag.lower().strip())
    return sorted(set(normalized))
```

---

## 🐛 Troubleshooting

### Feature disabled error

```
403: Tag generation feature is disabled
```

**Fix:** Enable in `settings.yaml`:
```yaml
features:
  mcp_tag_generator: true
```

### File not found

**Fix:** Use absolute paths or paths relative to where the server runs:
```bash
# Absolute
"/home/user/docs/tutorial.md"

# Relative to project root
"./docs/tutorial.md"
```

### LLM not responding

**Check:**
1. LLM provider is configured and running
2. API keys are set (if using cloud APIs)
3. Ollama is running (if using local models)

**Test LLM:**
```bash
curl http://localhost:9713/api/health
```

---

## 📚 Related

- [Parser documentation](../ingestion/parser.py) - How frontmatter is parsed
- [Retriever documentation](../rag/retriever.py) - How similar docs are found
- [LLM integration](../rag/llm.py) - How LLM calls are made
