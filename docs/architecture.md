# Architecture

mdkb is a search-first documentation tool with a Python backend and React frontend. This document explains how the pieces fit together.

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│  React SPA (Vite + TypeScript + Shadcn/ui)              │
│  Tabs: Chat │ Search │ Planner │ Browse │ Settings       │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP/SSE (/api/*)
┌────────────────────────▼────────────────────────────────┐
│  FastAPI Backend                                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Core Routers (9 modules)                        │   │
│  │  health │ search │ chat │ threads │ files        │   │
│  │  settings │ embeddings │ export │ scopes         │   │
│  ├──────────────────────────────────────────────────┤   │
│  │  Plugins (auto-discovered, feature-gated)        │   │
│  │  planner │ tags │ write_api │ ...                │   │
│  └──────────┬───────────────────────────┬───────────┘   │
│             │                           │               │
│  ┌──────────▼──────────┐  ┌─────────────▼───────────┐   │
│  │  Services           │  │  RAG Pipeline           │   │
│  │  chat_service       │  │  retriever (hybrid)     │   │
│  │  llm_service        │  │  llm (LiteLLM)          │   │
│  │  query_service      │  │  prompts                │   │
│  │  planner_service    │  │                         │   │
│  └──────────┬──────────┘  └─────────────┬───────────┘   │
│             │                           │               │
│  ┌──────────▼───────────────────────────▼───────────┐   │
│  │  Storage Layer                                   │   │
│  │  ChromaDB (vectors) │ SQLite ×5 (tracking,       │   │
│  │    chat, search, plans, scopes)                  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────┐  ┌────────────────────────────┐   │
│  │  Ingestion        │  │  Optional Modules          │   │
│  │  scanner          │  │  MCP tools (filesystem,    │   │
│  │  parser           │  │    terminal, tag generator) │   │
│  │  watcher          │  │  MCTS planner              │   │
│  │  indexer           │  │  Agent skills              │   │
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
│  Tools: search │ chat │ get_document │ list_documents   │
│         index_file │ list_sources │ stats               │
│  Transports: stdio │ SSE                                │
└─────────────────────────────────────────────────────────┘
```

## Request Lifecycle

1. **Frontend** makes HTTP requests to `/api/*`. Streaming responses (chat, summaries) use POST-based SSE via `fetch` + `ReadableStream`.
2. **Routers** handle request validation and call into services. Core routers (health, search, chat, etc.) are always registered. **Plugins** (`app/plugins/`) are auto-discovered at startup — each plugin exposes a feature flag and a router; only enabled plugins are registered.
3. **Auth middleware** (`app/auth.py`) checks the `X-MDKB-Key` header on all `/api/*` paths (except `/api/health`) when an API key is configured. Disabled when no key is set.
4. **Dependency injection** (`app/deps.py`) provides services via FastAPI's `Depends()`. All shared state lives on `app.state`, initialized in the async lifespan context manager (`app/main.py`).
5. **Services** contain business logic — conversation management, LLM health checks, query enhancement.
6. **Storage layer** persists data across six stores (see below).

## Storage

mdkb uses one vector database and five SQLite databases:

| Database | File | Purpose |
|----------|------|---------|
| **ChromaDB** | `data/chromadb/` | Vector embeddings for semantic search |
| **TrackingDB** | `data/tracking.db` | File index state, hashes, RAG inclusion flags |
| **ChatDB** | `data/chat.db` | Chat threads and messages |
| **SearchDB** | `data/search.db` | Search history, versions, AI summaries |
| **PlanDB** | `data/plans.db` | Saved planner plans and metadata |
| **ScopeDB** | `data/scopes.db` | Named source scopes (folder subsets) |

SQLite databases use `PRAGMA user_version` for schema migrations. Each database class carries a `_MIGRATIONS` list that is applied on open.

## Embedding Pipeline

1. **Scanner** (`app/ingestion/scanner.py`) discovers markdown files across configured source directories, respecting ignore patterns.
2. **Parser** (`app/ingestion/parser.py`) splits files into chunks by heading structure, with configurable size and overlap.
3. **Embedder** (`app/embeddings/embedder.py`) generates vector embeddings using ONNX models (runs on CPU, no PyTorch). Three models are available — see [embedding-models.md](embedding-models.md).
4. **Indexer** (`app/ingestion/indexer.py`) orchestrates the pipeline: scan → parse → embed → store in ChromaDB + track in TrackingDB.
5. **Watcher** (`app/ingestion/watcher.py`) uses `watchdog` to detect file changes and re-index incrementally. Runs in a background thread. The `FileWatcher` class supports adding directories at runtime — when a new source is added via the API, it starts watching immediately without a restart.
6. **Event Bus** (`app/events.py`) — the watcher publishes `IndexEvent` objects (indexed, deleted, error) to an `IndexEventBus`. SSE clients subscribe via `GET /api/index/events` to receive real-time notifications as files are processed.

## Retrieval & RAG

Search combines two strategies via the **Retriever** (`app/rag/retriever.py`):

- **Vector similarity**: Embeds the query and finds nearest neighbors in ChromaDB.
- **BM25 keyword matching**: Tokenizes all stored documents and scores by term frequency. Uses whole-word matching to avoid substring false positives.

The hybrid score is a weighted combination (configurable via `retrieval.bm25_weight`). Results below `score_threshold` are filtered out. Files marked as RAG-excluded in TrackingDB are post-filtered.

**RAG chat flow:**
1. User sends a message.
2. Retriever finds relevant chunks.
3. Chunks are assembled into a context prompt (`app/rag/prompts.py`).
4. LiteLLM sends the prompt + context to the active LLM provider (`app/rag/llm.py`).
5. Response streams back via SSE. Think-blocks (`<think>`) from reasoning models are stripped during streaming.

## LLM Integration

LLM calls go through **LiteLLM** (`app/rag/llm.py`), which provides a unified interface across providers. The fallback chain tries providers in order:

1. Active provider (configured in settings)
2. Other configured providers with valid API keys
3. Ollama (no key required)

Connection testing and model discovery for Ollama use `httpx` directly (`app/services/llm_service.py`). For providers with a model catalog plugin (e.g. Venice), the catalog provides the model list and capability info instead of relying on LiteLLM's registry. API keys are passed through from the provider config or the Settings UI.

## Plugin System

Optional routers live under `app/plugins/`. Each plugin is a directory with an `__init__.py` that exposes:

- `FEATURE_FLAG: str` — the feature flag name in `settings.yaml`
- `router: APIRouter` — the FastAPI router to register

At startup, `app/plugins/__init__.py` scans the directory, imports each plugin, checks its feature flag, and registers the router if enabled. Adding a new plugin requires no changes to core files — just create a new folder in `app/plugins/`.

Current plugins: `planner` (MCTS plan generation), `tags` (AI tag generation), `write_api` (document creation via HTTP).

### Model Catalogs

A separate plugin type lives under `app/plugins/catalogs/`. Each subdirectory provides a static model catalog for an LLM provider, exposing `get_model_ids()` and `get_model_info()`. These are used by `llm_service.build_model_list()` to populate the model dropdown and display pricing/context info in the UI. No feature flag is needed — catalogs are always active.

Current catalogs: `venice` (Venice.ai — 21 privacy-preserving chat models).

## Feature Flags

Optional modules are controlled by feature flags in `config/settings.yaml` under `features.*`. The flags are checked at startup (for plugin registration) and at runtime (for conditional behavior). Security-sensitive features (MCP tools) default to off — see [SECURITY.md](../SECURITY.md).

## MCP Server

`mcp_server.py` runs as a **separate process** alongside the FastAPI app. It exposes MDKB's core capabilities as MCP tools (search, chat, document access, indexing, stats) using the `mcp` SDK. Supports stdio (default) and SSE transports. See [mcp-server.md](mcp-server.md).

## Frontend

The React SPA (`frontend/`) communicates with the backend exclusively through the `/api/*` endpoints. Key patterns:

- **Hooks** (`frontend/src/hooks/`) encapsulate all API interaction and state management — one hook per domain (chat, search, files, settings, scopes, planner).
- **SSE streaming** uses POST-based fetch with `ReadableStream`, not `EventSource` (which only supports GET).
- **Retry logic** in `api.ts` handles server restarts with exponential backoff. Hooks retry on initial load failure.
- **State persistence** — some UI state (tab selection, panel sizes) is persisted to `localStorage` via `use-persisted-state`.
