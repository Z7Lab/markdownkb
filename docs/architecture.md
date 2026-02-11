# Architecture

mdkb is a search-first documentation tool with a Python backend and React frontend. This document explains how the pieces fit together.

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│  React SPA (Vite + TypeScript + Shadcn/ui)              │
│  Tabs: Chat │ Search │ Browse │ Settings                │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP/SSE (/api/*)
┌────────────────────────▼────────────────────────────────┐
│  FastAPI Backend                                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Routers (9 modules)                             │   │
│  │  health │ search │ chat │ threads │ files        │   │
│  │  settings │ embeddings │ export │ tags           │   │
│  └──────────┬───────────────────────────┬───────────┘   │
│             │                           │               │
│  ┌──────────▼──────────┐  ┌─────────────▼───────────┐   │
│  │  Services           │  │  RAG Pipeline           │   │
│  │  chat_service       │  │  retriever (hybrid)     │   │
│  │  llm_service        │  │  llm (LiteLLM)          │   │
│  │  query_service      │  │  prompts                │   │
│  └──────────┬──────────┘  └─────────────┬───────────┘   │
│             │                           │               │
│  ┌──────────▼───────────────────────────▼───────────┐   │
│  │  Storage Layer                                   │   │
│  │  ChromaDB (vectors) │ SQLite ×3 (tracking,       │   │
│  │                     │  chat history, search log)  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────┐  ┌────────────────────────────┐   │
│  │  Ingestion        │  │  Optional Modules          │   │
│  │  scanner          │  │  MCP tools (filesystem,    │   │
│  │  parser           │  │    terminal, tag generator) │   │
│  │  watcher          │  │  MCTS planner              │   │
│  │  indexer           │  │  Agent skills              │   │
│  └──────────────────┘  └────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
         │                        │
         ▼                        ▼
   ONNX Embeddings          LLM Providers
   (local CPU)              (Ollama / Anthropic / OpenAI)
```

## Request Lifecycle

1. **Frontend** makes HTTP requests to `/api/*`. Streaming responses (chat, summaries) use POST-based SSE via `fetch` + `ReadableStream`.
2. **Routers** handle request validation and call into services. Each router module covers one domain (search, chat, files, etc.).
3. **Dependency injection** (`app/deps.py`) provides services via FastAPI's `Depends()`. All shared state lives on `app.state`, initialized in the async lifespan context manager (`app/main.py`).
4. **Services** contain business logic — conversation management, LLM health checks, query enhancement.
5. **Storage layer** persists data across three stores (see below).

## Storage

mdkb uses one vector database and three SQLite databases:

| Database | File | Purpose |
|----------|------|---------|
| **ChromaDB** | `data/chromadb/` | Vector embeddings for semantic search |
| **TrackingDB** | `data/tracking.db` | File index state, hashes, RAG inclusion flags |
| **ChatDB** | `data/chat.db` | Chat threads and messages |
| **SearchDB** | `data/search.db` | Search history, versions, AI summaries |

SQLite databases use `PRAGMA user_version` for schema migrations. Each database class carries a `_MIGRATIONS` list that is applied on open.

## Embedding Pipeline

1. **Scanner** (`app/ingestion/scanner.py`) discovers markdown files across configured source directories, respecting ignore patterns.
2. **Parser** (`app/ingestion/parser.py`) splits files into chunks by heading structure, with configurable size and overlap.
3. **Embedder** (`app/embeddings/embedder.py`) generates vector embeddings using ONNX models (runs on CPU, no PyTorch). Three models are available — see [embedding-models.md](embedding-models.md).
4. **Indexer** (`app/ingestion/indexer.py`) orchestrates the pipeline: scan → parse → embed → store in ChromaDB + track in TrackingDB.
5. **Watcher** (`app/ingestion/watcher.py`) uses `watchdog` to detect file changes and re-index incrementally. Runs in a background thread.

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

Connection testing and model discovery for Ollama use `httpx` directly (`app/services/llm_service.py`).

## Feature Flags

Optional modules are controlled by feature flags in `config/settings.yaml` under `features.*`. The flags are checked at startup (for router registration) and at runtime (for conditional behavior). Security-sensitive features (MCP tools) default to off — see [SECURITY.md](../SECURITY.md).

## Frontend

The React SPA (`frontend/`) communicates with the backend exclusively through the `/api/*` endpoints. Key patterns:

- **Hooks** (`frontend/src/hooks/`) encapsulate all API interaction and state management — one hook per domain (chat, search, files, settings).
- **SSE streaming** uses POST-based fetch with `ReadableStream`, not `EventSource` (which only supports GET).
- **Retry logic** in `api.ts` handles server restarts with exponential backoff. Hooks retry on initial load failure.
- **State persistence** — some UI state (tab selection, panel sizes) is persisted to `localStorage` via `use-persisted-state`.
