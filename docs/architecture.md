# Architecture

mdkb is a chat-with-your-docs tool with a Python backend and React frontend. The core experience is RAG chat — everything else (search, graph, planner) is an optional plugin. This document explains how the pieces fit together.

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│  React SPA (Vite + TypeScript + Shadcn/ui)              │
│  Tabs: Chat │ Search │ Planner │ Graph │ Browse │ Settings │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP/SSE (/api/*)
┌────────────────────────▼────────────────────────────────┐
│  FastAPI Backend                                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Core Routers (8 modules)                        │   │
│  │  health │ chat │ threads │ files                 │   │
│  │  settings │ embeddings │ scopes │ plugins         │   │
│  ├──────────────────────────────────────────────────┤   │
│  │  Plugins (auto-discovered, feature-gated)        │   │
│  │  search │ export │ graph │ planner │ tags │ ...  │   │
│  └──────────┬───────────────────────────┬───────────┘   │
│             │                           │               │
│  ┌──────────▼──────────┐  ┌─────────────▼───────────┐   │
│  │  Services           │  │  RAG Pipeline           │   │
│  │  chat_service       │  │  retriever (hybrid)     │   │
│  │  llm_service        │  │  llm (direct SDK calls) │   │
│  │  query_service      │  │  prompts                │   │
│  │  planner_service    │  │                         │   │
│  │  deep_research      │  │                         │   │
│  └──────────┬──────────┘  └─────────────┬───────────┘   │
│             │                           │               │
│  ┌──────────▼───────────────────────────▼───────────┐   │
│  │  Storage Layer                                   │   │
│  │  ChromaDB (vectors) │ SQLite ×8 (tracking,       │   │
│  │    chat, search, plans, scopes, tags, buckets,   │   │
│  │    knowledge graph)                              │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────┐  ┌────────────────────────────┐   │
│  │  Ingestion        │  │  Shared Libraries (app/lib)│   │
│  │  scanner          │  │  filesystem, terminal,     │   │
│  │  parser           │  │  tag_generator             │   │
│  │  watcher          │  ├────────────────────────────┤   │
│  │  indexer           │  │  MCTS planner              │   │
│  │                    │  │  Knowledge graph            │   │
│  └──────────────────┘  └────────────────────────────┘   │
│                                                         │
│  ┌──────────────────┐  ┌────────────────────────────┐   │
│  │  Auth Middleware   │  │  API Key (X-MDKB-Key)     │   │
│  └──────────────────┘  └────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
         │                        │
         ▼                        ▼
   ONNX Embeddings          LLM Providers
   (local CPU)              (Ollama / Anthropic / OpenAI / Venice / ...)

┌─────────────────────────────────────────────────────────┐
│  MCP Server (mcp_server.py — separate process)          │
│  Core (22 tools):                                       │
│    health │ retrieve │ retrieve_documents │ chat        │
│    enhance_query │ deep_research │ get_file │ list_files│
│    list_threads │ list_sources │ list_models            │
│    list_scopes │ stats │ index_file │ save_file         │
│  Plugin:                                                │
│    summarize │ plan │ list_tags │ generate_tags         │
│    update_tags │ graph │ export_chat                    │
│    bucket_create │ bucket_add │ bucket_list              │
│    bucket_list_files │ bucket_search │ bucket_chat      │
│    bucket_delete                                        │
│  Transports: stdio │ SSE  │  read_only mode            │
│  Auth: X-MDKB-Key header │ ?token= query param         │
└─────────────────────────────────────────────────────────┘
```

## Core Components

Core is everything that loads regardless of plugin settings. Plugins add HTTP endpoints and UI features on top of core services.

### Routers (`app/routers/` — always registered)

| Router | Description |
|--------|-------------|
| `health` | Health check endpoint, SSE event stream for index progress |
| `chat` | RAG chat with LLM, thread creation, streaming responses |
| `threads` | List, rename, delete chat threads |
| `files` | File browser, indexing controls, folder listing, tag display |
| `settings` | Feature flags, system/retrieval prompts, retrieval config, plugin config |
| `sources` | Source directory management, ignore patterns, project roots |
| `llm` | LLM provider config, model listing, connection testing |
| `maintenance` | DB stats, clear, compact, log streaming |
| `embeddings` | Embedding model switching, download, status |
| `scopes` | Named folder + tag filter presets |

### Services (`app/services/`)

| Service | Description |
|---------|-------------|
| `chat_service` | RAG response generation (retrieve → prompt → LLM → stream) |
| `llm_service` | Provider health checks, model discovery, Ollama integration |
| `query_service` | Query enhancement — keyword extraction, term expansion |
| `planner_service` | MCTS planner orchestration (HTTP endpoint is in the planner plugin) |
| `deep_research` | Multi-angle research synthesis using MCTS (consumed by search plugin) |
| `graph_service` | Knowledge graph computation (HTTP endpoint is in the graph plugin) |

Note: `planner_service` and `graph_service` live in core because they are reusable — the plugins just add the HTTP + UI layer on top.

### Ingestion Pipeline (`app/ingestion/`)

| Module | Description |
|--------|-------------|
| `scanner` | File discovery across source directories, respecting ignore patterns |
| `parser` | Markdown splitting by headings, size-limited chunking, breadcrumbs, frontmatter |
| `indexer` | Orchestrates scan → parse → embed → store pipeline |
| `watcher` | Watchdog-based file change detection, incremental re-indexing |

### Storage (`app/storage/`)

| Store | File | Description |
|-------|------|-------------|
| VectorStore | `data/chromadb/` | ChromaDB vector embeddings for semantic search |
| TrackingDB | `data/tracking.db` | File index state, hashes, RAG inclusion flags |
| ChatDB | `data/chat.db` | Chat threads and messages |
| SearchDB | `data/searches.db` | Search history, versions, AI summaries |
| PlanDB | `data/plans.db` | Saved planner plans and metadata |
| PresetsDB | `data/presets.db` | Named retrieval setting templates |
| ScopeDB | `data/scopes.db` | Named scopes (folder + tag filters) |

### RAG (`app/rag/`)

| Module | Description |
|--------|-------------|
| `retriever` | Hybrid search — vector similarity + BM25 keyword matching, score fusion |
| `llm` | Anthropic SDK for Anthropic models, OpenAI-compatible SDK for everything else (Ollama, Venice, OpenAI, etc.), provider fallback chain, streaming |
| `prompts` | System and user prompt templates for chat, summaries, query enhancement |

### Shared Libraries (`app/lib/`)

| Module | Description |
|--------|-------------|
| `filesystem` | File browsing utilities (directory tree formatting) |
| `terminal` | Terminal command execution helpers |
| `tag_generator` | Tag suggestion from content, LLM-based generation, frontmatter writing |

### Infrastructure

| Module | Description |
|--------|-------------|
| `app/auth.py` | API key middleware (`X-MDKB-Key` header) |
| `app/config/` | Settings singleton, mixin-based config, YAML persistence |
| `app/deps.py` | FastAPI dependency injection (Depends providers) |
| `app/embeddings/` | ONNX embedding model registry, CPU inference |
| `app/events.py` | IndexEventBus for real-time SSE notifications |
| `app/main.py` | Application entry point, lifespan context manager |
| `app/api.py` | App factory, router registration, plugin discovery |

## Request Lifecycle

1. **Frontend** makes HTTP requests to `/api/*`. Streaming responses (chat, summaries) use POST-based SSE via `fetch` + `ReadableStream`.
2. **Routers** handle request validation and call into services. Core routers (health, chat, threads, files, settings, embeddings, scopes, plugins) are always registered. **Plugins** (`app/plugins/` and `data/plugins/`) are auto-discovered at startup — each plugin exposes a feature flag and a router; only enabled plugins are registered.
3. **Auth middleware** (`app/auth.py`) checks the `X-MDKB-Key` header on all `/api/*` paths (except `/api/health`) when an API key is configured via Docker secret or env var. Uses `hmac.compare_digest()` for timing-safe comparison. Disabled when no key is set.
4. **Dependency injection** (`app/deps.py`) provides services via FastAPI's `Depends()`. All shared state lives on `app.state`, initialized in the async lifespan context manager (`app/main.py`).
5. **Services** contain business logic — conversation management, LLM health checks, query enhancement.
6. **Storage layer** persists data across seven stores (see below).

## Storage

mdkb uses one vector database and nine SQLite databases:

| Database | File | Purpose |
|----------|------|---------|
| **ChromaDB** | `data/chromadb/` | Vector embeddings for semantic search |
| **TrackingDB** | `data/tracking.db` | File index state, hashes, RAG inclusion flags |
| **ChatDB** | `data/chat.db` | Chat threads and messages |
| **SearchDB** | `data/search.db` | Search history, versions, AI summaries |
| **PlanDB** | `data/plans.db` | Saved planner plans and metadata |
| **PresetsDB** | `data/presets.db` | Named retrieval setting templates |
| **ScopeDB** | `data/scopes.db` | Named scopes (folder + tag filters) |
| **TagDB** | `data/tags.db` | File-to-tag mappings (owned by tags plugin) |
| **BucketDB** | `data/buckets.db` | Temporary bucket metadata (owned by buckets plugin) |
| **KnowledgeGraphDB** | `data/mdkb_kg.db` | Entities, typed relationships, extraction cache (owned by graph plugin) |

The knowledge graph database is intentionally separate from the tracking database. Embedding model switches clear ChromaDB vectors and tracking state, but KG data (which is LLM-extracted, not embedding-dependent) survives intact.

SQLite databases use `PRAGMA user_version` for schema migrations. Each database class carries a `_MIGRATIONS` list that is applied on open. Plugin-owned databases (e.g. TagDB) follow the same patterns but are created by the plugin's `on_startup` hook rather than in core startup.

## Embedding Pipeline

1. **Scanner** (`app/ingestion/scanner.py`) discovers markdown files across configured source directories, respecting ignore patterns.
2. **Parser** (`app/ingestion/parser.py`) splits files into chunks by heading structure, with configurable size and overlap.
3. **Embedder** (`app/embeddings/embedder.py`) generates vector embeddings using ONNX models (runs on CPU, no PyTorch). Three models are available — see [embedding-models.md](embedding-models.md).
4. **Indexer** (`app/ingestion/indexer.py`) orchestrates the pipeline: scan → parse → embed → store in ChromaDB + track in TrackingDB.
5. **Watcher** (`app/ingestion/watcher.py`) uses `watchdog` to detect file changes and re-index incrementally. Runs in a background thread. The `FileWatcher` class supports adding directories at runtime — when a new source is added via the API, it starts watching immediately without a restart. The observer is cleanly stopped during application shutdown.
6. **Event Bus** (`app/events.py`) — the watcher publishes `IndexEvent` objects (indexed, deleted, error) to an `IndexEventBus`. SSE clients subscribe via `GET /api/index/events` to receive real-time notifications as files are processed.

## Retrieval & RAG

Search combines two strategies via the **Retriever** (`app/rag/retriever.py`):

- **Vector similarity**: Embeds the query and finds nearest neighbors in ChromaDB.
- **BM25 keyword matching**: Tokenizes all stored documents and scores by term frequency. Uses whole-word matching to avoid substring false positives.

The hybrid score is a weighted combination (configurable via `retrieval.bm25_weight`). Results below `score_threshold` are filtered out. Files marked as RAG-excluded in TrackingDB are post-filtered. When a scope with tags is active, results are further filtered to documents matching any of the scope's tags (OR logic).

**RAG chat flow:**
1. User sends a message.
2. Retriever finds relevant chunks.
3. Chunks are assembled into a context prompt (`app/rag/prompts.py`).
4. The prompt + context is sent to the active LLM provider via the anthropic or openai SDK (`app/rag/llm.py`).
5. Response streams back via SSE. Think-blocks (`<think>`) from reasoning models are stripped during streaming.

## LLM Integration

LLM calls go through `app/rag/llm.py`, which routes to the **anthropic** or **openai** SDK based on the `provider/model` string format. Anthropic models use the Messages API directly; everything else (OpenAI, Ollama, Venice, and other OpenAI-compatible providers) uses the openai SDK with a custom `base_url`. The fallback chain tries providers in order:

1. Active provider (configured in settings)
2. Other configured providers with valid API keys
3. Ollama (no key required)

SDK clients are cached with `lru_cache` for connection reuse. Ollama gets special handling: the base URL auto-appends `/v1` if missing, and `num_ctx` is passed via `extra_body`. Connection testing and model discovery for Ollama use `httpx` directly (`app/services/llm_service.py`). For providers with a model catalog plugin (e.g. Venice), the catalog provides the model list and capability info. API keys are resolved from Docker secrets (`/run/secrets/<provider>_api_key`) or environment variables (`<PROVIDER>_API_KEY`) — never from YAML config.

## Plugin System

Plugins live in two locations:

- **Builtin** — `app/plugins/<name>/` — shipped with the application
- **External** — `data/plugins/<name>/` — user-installed (persisted via Docker volume mount)

Each plugin is a directory with an `__init__.py` that exposes:

- `FEATURE_FLAG: str` — metadata identifier for the plugin
- `router: APIRouter` — the FastAPI router to register

At startup, `app/plugins/__init__.py` scans both directories, imports each plugin, checks `plugins.<name>.enabled` in settings, and registers the router if enabled. External plugins get their parent directory added to `sys.path` for import resolution. Adding a new plugin requires no changes to core files.

Plugins can optionally define `on_startup(app)` and `on_shutdown(app)` hooks in their `__init__.py`. These are called after core services are initialized (startup) and before core databases are closed (shutdown), allowing plugins to create their own databases, register hooks with core dispatchers, or run migrations.

### Plugin Manifests

Plugins may include a `plugin.yaml` manifest providing display metadata, endpoint declarations, and config schemas. The UI uses this to render the plugin management page with auto-generated configuration forms. Example:

```yaml
name: search
display_name: Search & Summaries
description: Semantic search with history and AI summaries.
version: 1.0.0
author: mdkb
icon: search
category: search
feature_flag: search
requires: []

endpoints:
  - method: POST
    path: /api/search
    description: Semantic search

config:
  chunk_multiplier:
    type: integer
    default: 10
    min: 1
    max: 100
    label: Chunk multiplier
    description: Chunks fetched per result
```

Config schema types: `boolean` (toggle), `integer` (number input with optional min/max), `string` (text input).

### Plugin Installation & Removal

External plugins can be installed from GitHub via `POST /api/plugins/install`. The flow:

1. Clone the repo (shallow, `--depth 1`) to a temp directory
2. If the URL includes a subdirectory (e.g. `/tree/main/plugins/my-plugin`), extract that directory
3. Validate: must have `__init__.py` with `FEATURE_FLAG` and `router`
4. Install `requirements.txt` if present
5. Copy to `data/plugins/<name>/`
6. Add `plugins.<name>.enabled: false` to settings
7. Requires a container restart to activate

Builtin plugins cannot be uninstalled — only disabled via `plugins.<name>.enabled`. External plugins can be fully removed via `DELETE /api/plugins/{name}`.

URL formats accepted: `https://github.com/user/repo`, `https://github.com/user/repo/tree/main/path/to/plugin`, `user/repo`.

### Plugin Configuration

Each plugin's `enabled` flag and config live together under `plugins.<name>` in `config/settings.yaml`:

```yaml
plugins:
  search:
    enabled: true
    chunk_multiplier: 10
    exact_phrase_matching: true
  graph:
    enabled: true
```

Plugins read their config via `Settings.get_plugin_config("name")` (which filters out the `enabled` key) and define their own defaults internally. A generic API (`GET/PUT /api/settings/plugins/{name}`) allows reading and updating any plugin's config without changes to core code.

Current builtin plugins: `search` (search with history and AI summaries), `export` (conversation export), `graph` (knowledge graph visualization), `planner` (MCTS plan generation), `tags` (tag storage, CRUD, auto-tagging, and optional AI generation), `write_api` (document creation via HTTP), `buckets` (temporary scoped document collections with independent vector storage, search, and chat).

**Deep Research** is not a plugin with its own routes — it's a shared service (`app/services/deep_research.py`) that uses the MCTS engine (`app/planner/`) to run multi-angle research synthesis. It is consumed by the search plugin (via the `deep_research` flag on the summarize endpoint) and can be used by any other plugin. Gated by `core.deep_research`. Its config lives under `services.deep_research`.

### Model Catalogs

A separate plugin type lives under `app/plugins/catalogs/`. Each subdirectory provides a static model catalog for an LLM provider, exposing `get_model_ids()` and `get_model_info()`. These are used by `llm_service.build_model_list()` to populate the model dropdown and display pricing/context info in the UI. No feature flag is needed — catalogs are always active.

Current catalogs: `venice` (Venice.ai — 21 privacy-preserving chat models).

## Settings Structure

Configuration is split into four sections in `config/settings.yaml`:

- **`core:`** — behaviour toggles for built-in features (rag_chat, file_watcher, etc.)
- **`mcp:`** — MCP tool flags (read_only, allow_bucket_writes, save_document, filesystem, terminal)
- **`plugins:`** — each plugin has `enabled` + config together (`plugins.<name>.enabled`)
- **`services:`** — shared service config (deep_research iterations, etc.)

Legacy `features:` layouts are auto-migrated on first startup and saved to disk. Security-sensitive features (MCP tools) default to off — see [SECURITY.md](../SECURITY.md).

## MCP Server

`mcp_server.py` runs as a **separate process** alongside the FastAPI app. It exposes MDKB's core capabilities as MCP tools (search, chat, document access, indexing, stats) using the `mcp` SDK. Supports stdio (default) and SSE transports. See [mcp-server.md](mcp-server.md).

## Frontend

The React SPA (`frontend/`) communicates with the backend exclusively through the `/api/*` endpoints. Key patterns:

- **Hooks** (`frontend/src/hooks/`) encapsulate all API interaction and state management — one hook per domain (chat, search, files, settings, scopes, planner, graph).
- **SSE streaming** uses POST-based fetch with `ReadableStream`, not `EventSource` (which only supports GET).
- **Retry logic** in `api.ts` handles server restarts with exponential backoff. Hooks retry on initial load failure.
- **State persistence** — some UI state (tab selection, panel sizes) is persisted to `localStorage` via `use-persisted-state`.
