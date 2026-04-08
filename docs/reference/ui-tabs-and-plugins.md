# UI Tabs and Plugins

mdkb's web UI has seven tabs. Some are always available (core), some only appear when their plugin is enabled in Settings.

## Core Tabs (always available)

### Chat

The primary interface. Ask questions about your knowledge base and get AI-powered answers with source citations. Supports streaming responses, conversation threads, and scoped filtering.

**Requires:** An LLM provider configured in Settings > Chat Model. Without one, chat will prompt you to set up a provider.

**Sidebar:** Conversation history, scope filter, tag filter, bucket selector, model picker.

### Files

Browse, search, and manage all indexed documents. View file contents, edit tags, toggle RAG inclusion, trigger re-indexing, and see indexing status.

**Sidebar:** None — full-width file table.

### Settings

Configure everything: LLM provider, embedding model, sources, scopes, plugins, retrieval tuning, prompts, MCP tools, and system maintenance.

## Plugin Tabs

These tabs appear in the navigation bar only when their plugin is enabled in Settings > Plugins.

### Search

Full-text semantic search with AI-generated summaries. Search results show relevance scores, source documents, and chunk-level matches. Supports deep research mode (multi-angle MCTS synthesis), search history with versioning, and re-querying.

**Plugin:** `search` (enabled by default)
**Requires:** Embedding model installed. LLM required for AI summaries.

**Sidebar:** Search history, scope filter, tag filter, bucket selector.

### Planner

AI-powered implementation planning using MCTS (Monte Carlo Tree Search). Describe what you want to build and get a structured plan with explored approaches, source references, and optional skill reviews.

**Plugin:** `planner` (disabled by default)
**Requires:** LLM provider configured.

**Sidebar:** Saved plans, scope filter, tag filter, bucket selector.

### Doc Map

3D visualization of document similarity. Documents appear as nodes, with edges connecting similar documents. Clusters are color-coded. Includes word clouds, search highlighting, and interactive exploration.

**Plugin:** `docmap` (enabled by default)
**Requires:** Embedding model installed. WebGL support in the browser.

**Sidebar:** Scope filter, similarity threshold slider, spread control, search filter, word cloud toggle, refresh button.

### Knowledge Graph

3D visualization of entities and relationships extracted from your documents. Shows concepts, technologies, patterns, and how they relate to each other across your knowledge base.

**Plugin:** `knowledge_graph` (disabled by default)
**Requires:** LLM provider configured (entity extraction is LLM-powered). Run "Extract Entities" from the sidebar to build the graph.

**Sidebar:** Entity/relationship stats, type badges, extraction controls (start/cancel/progress).

## Builtin Plugins

All plugins live in `app/plugins/<name>/` and are toggled via `plugins.<name>.enabled` in settings.yaml or the Settings UI. Disabling a plugin removes its tab, API routes, and background processing — zero trace when off.

| Plugin | Default | Tab | Description |
|--------|---------|-----|-------------|
| `search` | on | Search | Semantic search with AI summaries, history, deep research |
| `tags` | on | — | Tag storage, frontmatter extraction, manual tagging, AI generation |
| `docmap` | on | Doc Map | Document similarity visualization (3D force graph) |
| `catalogs` | on | — | Model catalog providers (Ollama, Venice) for the Settings model picker |
| `export` | on | — | Export chat conversations as markdown or JSON |
| `converter` | on | — | Batch convert DOCX, PDF, HTML to markdown via Pandoc |
| `planner` | off | Planner | MCTS implementation planning with skill reviews |
| `knowledge_graph` | off | Knowledge Graph | Entity extraction and relationship visualization |
| `buckets` | off | — | Temporary scoped document collections with independent vector storage |
| `write_api` | off | — | MCP/API write access (save documents, index files) |

Plugins marked "on" are enabled in the default configuration. Plugins marked "off" need to be explicitly enabled — either in `config/settings.yaml` or via Settings > Plugins in the UI.

## Enabling a Plugin

### From the UI

Go to **Settings > Plugins**, find the plugin, and toggle it on. Some plugins require a container restart to take effect.

### From settings.yaml

```yaml
plugins:
  planner:
    enabled: true
  knowledge_graph:
    enabled: true
  buckets:
    enabled: true
```

## Plugin Dependencies

Some plugins have external dependencies:

| Plugin | Dependency | Notes |
|--------|-----------|-------|
| `converter` | Pandoc | System package, not bundled in Docker image. Install separately. |
| `knowledge_graph` | LLM provider | Entity extraction calls the configured LLM. |
| `planner` | LLM provider | Plan generation calls the configured LLM. |
| `tags` (AI generation) | LLM provider | Optional `ai_generation: true` sub-flag for AI-powered tagging. |

Plugins without an LLM dependency (search, docmap, export, buckets, catalogs) work with just the embedding model.
