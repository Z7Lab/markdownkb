# Knowledge Graph Plugin

Extract entities and typed relationships from your indexed documents using LLM, building a queryable knowledge graph. Entities (concepts, tools, technologies, processes, etc.) are connected by typed relationships (uses, is-a, part-of, depends-on, etc.).

**Feature flag:** `knowledge_graph`
**Prefix:** `/api/knowledge-graph`

## How It Works

1. **Extraction is triggered manually** — either globally (all indexed files) or per-file from the Files tab.
2. For each file, chunks are batched and sent to the configured LLM with a structured extraction prompt.
3. The LLM returns entities and relationships as JSON, which are stored in a dedicated SQLite database.
4. Extracted data is cached per-chunk (content hash) — re-running extraction on unchanged files skips already-extracted chunks.

Extraction is decoupled from indexing. Enabling this plugin does not slow down the indexing pipeline. You choose when to extract.

## Entity and Relationship Types

**Entity types:** concept, technology, tool, process, pattern, standard, organization, person, metric, principle

**Relationship types:** uses, is-a, part-of, relates-to, implements, depends-on, produces, defines, contradicts, extends, requires, enables, measures, applies-to

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/knowledge-graph/extract` | Start background extraction over all indexed files |
| POST | `/api/knowledge-graph/extract-file` | Extract entities from a single file (`?path=X`) |
| GET | `/api/knowledge-graph/extract/status` | Extraction progress |
| POST | `/api/knowledge-graph/extract/cancel` | Cancel running extraction |
| GET | `/api/knowledge-graph/data` | All entities and relationships (with optional type filters) |
| GET | `/api/knowledge-graph/entity` | Single entity with all connections (`?name=X`) |
| GET | `/api/knowledge-graph/path` | BFS shortest path between two entities (`?source=X&target=Y`) |
| GET | `/api/knowledge-graph/stats` | Entity and relationship counts |
| GET | `/api/knowledge-graph/file-entity-counts` | Entity count per file |
| POST | `/api/knowledge-graph/clear` | Clear all KG data |

## Files Tab Integration

When this plugin is enabled:

- An **Entities** column appears in the Files tab showing the entity count per file.
- An **Extract Entities** action button (wand icon) appears for indexed files.
- Per-file extraction is synchronous — results appear immediately after completion.

When this plugin is disabled, these UI elements are completely removed.

## MCP Tools

| Tool | Description |
|------|-------------|
| `query_knowledge_graph` | Query entities and relationships by type |
| `get_kg_entity` | Get entity details with all incoming/outgoing connections |
| `find_relationship_path` | BFS shortest path between two entities |

## Storage

- **KnowledgeGraphDB** (`data/mdkb_kg.db`) — separate SQLite database with tables for entities, relationships, and extraction cache.
- Survives embedding model switches (KG data is LLM-extracted, not embedding-dependent).
- Per-file provenance — every entity and relationship links back to its source file via `source_path`.
- Cascade deletion — removing a file clears all its entities and relationships.

## Configuration

```yaml
plugins:
  knowledge_graph:
    enabled: false    # Requires LLM — opt-in
```

## Performance

Extraction speed depends on the LLM. With a local Ollama model (~8B params), expect 5-15 seconds per file. For large corpora, use global extraction and let it run in the background — it's cancellable and progress is tracked.

The extraction cache means re-running on an unchanged corpus is nearly instant.

## Dependencies

- Configured LLM provider (Ollama, Anthropic, OpenAI, or any OpenAI-compatible endpoint)
- `app.ingestion.parser` — markdown parsing and chunking (same as indexing)
- `app.rag.llm` — LLM completion calls
