# Tags Plugin

Tag storage, CRUD, folder-based auto-tagging, and optional AI-powered tag generation for markdown files.

**Feature flag:** `tags`
**Prefix:** `/api` (endpoints under `/api/v1/tags` and `/api/v1/files/tags`)
**Database:** `data/tags.db` (plugin-owned SQLite)

## Overview

The tags plugin owns all tag-related functionality. When enabled, it:

1. Creates and manages its own SQLite database (`TagDB`) for file-to-tag mappings
2. Registers tag resolution hooks so core features (chat, scopes) can filter by tags without importing the plugin
3. Provides CRUD, bulk operations, folder-based auto-tagging, and optional AI generation

When disabled, tag filtering becomes a no-op — chat, search, graph, and planner work without tag filtering. The Browse tab shows files without tags.

## Endpoints

### Tag CRUD

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/tags` | List unique tags (paginated) |
| PUT | `/api/v1/files/tags` | Update tags on a file |
| PUT | `/api/v1/files/bulk-tags` | Bulk update tags (add/remove/replace) |

### Auto-Tag (folder-structure based)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/files/auto-tag-preview` | Preview auto-tag assignments by folder pattern (dry run) |
| POST | `/api/v1/files/auto-tag-apply` | Apply auto-tag assignments from preview |

### AI Tag Generation (requires `plugins.tags.ai_generation`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/tags/generate` | Generate AI tags for a markdown file |
| POST | `/api/v1/tags/apply` | Apply tags to a file's frontmatter |
| POST | `/api/v1/tags/bulk` | Bulk-tag files in a directory |

AI endpoints require `plugins.tags.ai_generation: true` in settings. This allows basic tagging to work without enabling AI generation.

## Lifecycle

The plugin uses lifecycle hooks to initialize after core services are ready:

- **`on_startup(app)`**: Creates TagDB, runs one-time migration from TrackingDB (if TagDB is empty), registers resolver hooks with `app/tag_utils.py`
- **`on_shutdown(app)`**: Closes TagDB connection

## Tag Resolution Protocol

Core code never imports this plugin directly. Instead, `app/tag_utils.py` provides a dispatcher with module-level hooks:

- `register_resolver(fn)` — called at startup, enables `resolve_tag_paths()` for scope/ad-hoc tag filtering
- `register_tag_lister(fn)` — enables `get_all_tags()` for the files list and tag filter UI
- `register_file_tags_lister(fn)` — enables `get_all_file_tags()` for enriching file listings
- `register_tags_hook(fn)` — enables `notify_tags_extracted()` so the indexer can store frontmatter tags

If no plugin registers, all these functions return safe no-op values (empty lists, `None`).

## Migration

On first startup with the tags plugin enabled, `on_startup` checks if TagDB is empty. If so, it copies existing tags from TrackingDB's `file_metadata` table. This is a one-time migration — after that, TagDB is the sole authority for tags.

## Dependencies

- `app.tag_utils` — dispatcher hooks for core integration
- `app.rag.retriever` — similar document lookup (AI generation only)
- `app.lib.tag_generator` — LLM-based tag generation and file modification (AI generation only)
