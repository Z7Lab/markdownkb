# Scopes and Filtering

Scopes let you focus your knowledge base on a subset of your documents. Instead of searching, chatting, or visualizing against everything, you can narrow the context to specific folders, tags, or both — and exclude files that match patterns you don't want.

## How Scopes Work

A scope is a named filter with three parts:

- **Project Directories** — select one or more project roots; all their indexed subdirectories are included
- **Watch Directories** — individual source directories to include (e.g. `/home/user/docs/project-a`)
- **Tags** — markdown frontmatter tags to include (e.g. `architecture`, `decisions`)
- **Exclude patterns** — glob patterns for files to skip (e.g. `agent-reviewed-*`, `**/archive/**`)

When you select a scope, only documents matching the folder/tag criteria (minus any excluded patterns) appear in results. This applies everywhere — Chat, Search, Planner, and Doc Map all respect the active scope.

## Creating Scopes

Go to **Settings > Scopes** and click **New Scope**:

1. Give it a name (e.g. "Infrastructure Docs")
2. Check one or more Project Directories, or individual Watch Directories
3. Optionally add tags (documents with any of these tags are included)
4. Optionally add exclude patterns (files matching these are filtered out)
5. Click **Create**

When a scope has both folders and tags, they use **OR logic** — documents from the selected folders plus documents matching the selected tags are all included.

## Exclude Patterns

Exclude patterns use glob syntax and match against both the full file path and the filename:

| Pattern | What it excludes |
|---------|-----------------|
| `agent-reviewed-*` | Any file starting with `agent-reviewed-` |
| `**/archive/**` | Files in any directory named `archive` |
| `*.backup.md` | Any `.backup.md` file |
| `**/internal/**` | Files in any `internal` directory |
| `draft-*` | Files starting with `draft-` |

Exclude patterns are applied after folder and tag filtering. A file that matches an included folder but also matches an exclude pattern will be excluded.

## Using Scopes in the Sidebar

Every tab (Chat, Search, Planner, Doc Map) has a **Scopes** section in the sidebar:

- **All sources** is checked by default — no filtering, everything is included
- Check one or more scopes to narrow results to those subsets
- Scopes with exclude patterns show a count indicator (e.g. "1 excl.")
- The Scopes label highlights and shows a badge when filtering is active
- **Filter state persists** across tab switches and page refreshes via localStorage

## Markdown Tags

Below Scopes, the sidebar shows **Markdown Tags** — these are ad-hoc tag filters extracted from your documents' YAML frontmatter:

```yaml
---
tags:
  - architecture
  - decisions
---
```

Checking a markdown tag filters results to documents that have that tag, regardless of which scope is active. Tags and scopes combine with OR logic.

Tags are extracted automatically during indexing. If you add tags to a document's frontmatter, they'll appear in the sidebar after the file is re-indexed (the file watcher handles this automatically when the file changes).

## Scope vs Tag: When to Use Which

- **Scopes** are for folder-based organization — "all docs in this project directory." Create them in Settings, use them across sessions.
- **Markdown tags** are for content-based organization — "all docs tagged `architecture` regardless of which folder they're in." Add them to your document frontmatter.
- **Combine both** — a scope can include folders AND require specific tags. Or use a scope for the folder and then further filter by ad-hoc tags in the sidebar.

## API

Scopes are managed via the `/api/v1/scopes` endpoints:

- `GET /api/v1/scopes` — list all scopes
- `POST /api/v1/scopes` — create a scope (`name`, `folders`, `tags`, `exclude_patterns`)
- `PUT /api/v1/scopes/{id}` — update a scope
- `DELETE /api/v1/scopes/{id}` — delete a scope

When making search, chat, or planner requests, pass `scope_ids` (comma-separated) to filter by scope. Pass `ad_hoc_tags` to filter by markdown tags.
