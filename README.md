# mdkb — Markdown Knowledge Base

**Search-first documentation exploration for your markdown knowledge base.**

Combines semantic vector search with keyword matching (hybrid BM25+vector), tracks search history with versioning, and lets you explore findings through conversational AI. Purpose-built for documentation, not general chat.

Python (FastAPI) backend + React (Vite + TypeScript + Shadcn/ui) frontend.

## Quick Start

```bash
cp config/settings.yaml.example config/settings.yaml  # first time only
./run.sh
```

Edit `config/settings.yaml` to add your source directories and LLM API keys. The example file has sensible defaults for everything else.

Creates `.venv`, installs Python and Node dependencies if needed, starts both services. Open `http://localhost:5173` (dev) or `http://localhost:9713` (production).

## run.sh

```bash
./run.sh           # dev mode (default): hot reload, backend:9713 + Vite:5173
./run.sh -p        # production: builds frontend, serves everything on :9713
./run.sh -b        # backend only, no frontend
./run.sh -l        # use pinned deps from requirements.lock
./run.sh -h        # help
```

- Auto-creates `.venv` and installs `requirements.txt` if missing
- Auto-installs `frontend/node_modules` if missing
- Kills existing processes on ports before starting
- Ctrl+C kills everything
- Health checks both services with color-coded status
- Reads `.env` for port overrides (copy `.env.example` to `.env`)

## Docker

```bash
cp config/settings.yaml.example config/settings.yaml  # add your source dirs and LLM config
cp .env.example .env                                   # edit if needed (ports, Ollama IP, API keys)
make build && make up
```

Your home directory is mounted read-only into the container, so paths in `settings.yaml` work identically whether running with Docker or natively. Add or remove source directories from the **Settings** tab — no Docker restart needed.

The container binds to **localhost only** by default and runs as a non-root user. Set `MDKB_HOST=0.0.0.0` in `.env` to expose it to your network.

### Makefile

```bash
make help       # show all targets
make build      # build Docker image
make up         # start container (detached)
make down       # stop container
make logs       # tail container logs
make shell      # open a shell in the container
make restart    # restart container
make clean      # stop container and remove image
```

### Running without Docker

Docker is optional. You can run mdkb directly with:

```bash
./run.sh        # or: make dev
```

This creates a `.venv`, installs dependencies, and starts both services locally. See [run.sh](#runsh) above for all options.

## Configuration

Edit `config/settings.yaml` or use the **Settings** tab in the UI.

### Sources

| Key | Default | Description |
|-----|---------|-------------|
| `sources` | `[./docs]` | Directories to scan for markdown files |
| `global_ignore` | node_modules, .git, etc. | Glob patterns to skip |

### Embeddings

| Key | Default | Description |
|-----|---------|-------------|
| `embeddings.model` | `all-MiniLM-L6-v2` | Embedding model (ONNX, no PyTorch) |
| `embeddings.chunk_size` | `512` | Max characters per chunk |
| `embeddings.chunk_overlap` | `50` | Overlap between chunks |

Three embedding models are available: `all-MiniLM-L6-v2`, `all-MiniLM-L12-v2`, and `bge-small-en-v1.5`. Install and switch between them from the **Settings** tab. See [docs/embedding-models.md](docs/embedding-models.md) for details.

### LLM Providers

| Key | Default | Description |
|-----|---------|-------------|
| `llm.providers` | anthropic, openai, ollama | LLM backends with `name`, `model`, `api_key`, `api_base` |
| `llm.active_provider` | `ollama` | Which provider to use |
| `llm.temperature` | `0.3` | Response randomness |
| `llm.max_tokens` | `2048` | Max response length |

Model names use [LiteLLM format](https://docs.litellm.ai/docs/providers): `provider/model` (e.g. `ollama/qwen3:8b`, `anthropic/claude-3-5-sonnet-20241022`).

Providers without an `api_key` are skipped (except Ollama). If the active provider fails, others are tried as fallbacks.

### Retrieval

| Key | Default | Description |
|-----|---------|-------------|
| `retrieval.top_k` | `5` | Chunks to retrieve per query |
| `retrieval.score_threshold` | `0.3` | Minimum similarity score |
| `retrieval.hybrid_search` | `true` | Combine vector + BM25 keyword search |
| `retrieval.bm25_weight` | `0.5` | Keyword vs vector balance |
| `retrieval.intelligent_search.enabled` | `false` | LLM-powered query enhancement (keyword extraction, acronym expansion) |

### Storage

| Key | Default | Description |
|-----|---------|-------------|
| `storage.persist_directory` | `./data/chromadb` | ChromaDB vector store location |
| `storage.collection_name` | `mdkb` | ChromaDB collection name |

### Server

| Key | Default | Description |
|-----|---------|-------------|
| `server.host` | `127.0.0.1` | Bind address |
| `server.port` | `9713` | Backend port |
| `plans.save_directory` | `./data/plans` | Where saved plans are written |

### Features

| Key | Default | Description |
|-----|---------|-------------|
| `features.rag_chat` | `true` | Chat with RAG |
| `features.file_watcher` | `true` | Auto-reindex on file changes |
| `features.mcp_filesystem` | `false` | MCP file browsing tool |
| `features.mcp_terminal` | `false` | MCP terminal tool |
| `features.mcp_tag_generator` | `false` | AI tag generation for markdown files |
| `features.mcts_planner` | `false` | MCTS plan generation |
| `features.agent_skills` | `false` | Agent skill system |
| `features.diagnostics` | `false` | Diagnostic endpoints |
| `features.rate_limiting` | `false` | API rate limiting (slowapi) |

## LLM Setup

mdkb calls LLMs over the network — it doesn't run them locally.

**Anthropic / OpenAI:** Set your API key in `config/settings.yaml` or via environment variable (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).

**Ollama on another machine:** See [docs/ollama-remote-setup.md](docs/ollama-remote-setup.md).

## API

All endpoints under `http://localhost:9713/api/`. Interactive docs at `http://localhost:9713/docs` (Swagger UI).

### Health & Stats

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/health/llm` | Lightweight LLM health check (for status polling) |
| GET | `/api/stats` | Index statistics (files, chunks, embedding model, provider) |

### Search

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/search` | Semantic search with optional query enhancement |
| GET | `/api/searches` | List search history (paginated) |
| GET | `/api/searches/{id}/load` | Load historical search version with preserved results |
| GET | `/api/searches/{id}/versions` | Get all versions of a search (original + re-queries) |
| DELETE | `/api/searches/{id}` | Delete a search from history |
| POST | `/api/search/summarize` | AI summary of search results (streaming) |
| POST | `/api/search/enhance-query` | LLM query enhancement (keywords, acronyms) |
| GET | `/api/folders` | List unique folders from indexed documents |
| GET | `/api/tags` | List unique tags from indexed documents |

### Chat

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | RAG chat (non-streaming) |
| POST | `/api/chat/stream` | SSE streaming chat |
| DELETE | `/api/chat/history` | Clear conversation |
| POST | `/api/chat/save-plan` | Save response as markdown |

### Threads

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/threads` | List chat threads (paginated) |
| GET | `/api/threads/{id}/messages` | Get messages for a thread |
| DELETE | `/api/threads/{id}` | Delete a thread |
| PATCH | `/api/threads/{id}` | Rename a thread |

### Files

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/files` | List all discovered files (paginated) |
| GET | `/api/file` | Read file content |
| GET | `/api/file/status` | Get status of a single file |
| PUT | `/api/files/toggle-rag` | Toggle RAG inclusion for a file |
| POST | `/api/files/unindex` | Remove file chunks from index |
| POST | `/api/files/index` | Index a single file |
| POST | `/api/files/reindex` | Re-embed a file's chunks |

### Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings` | Get full settings |
| GET | `/api/sources` | List source directories |
| POST | `/api/sources` | Add source directory |
| DELETE | `/api/sources` | Remove source directory |
| POST | `/api/ignore-patterns` | Add ignore pattern |
| DELETE | `/api/ignore-patterns` | Remove ignore pattern |
| PUT | `/api/settings/provider` | Save LLM provider config |
| POST | `/api/settings/test-connection` | Test LLM connectivity |
| POST | `/api/settings/ping-model` | Ping a specific model |
| POST | `/api/settings/refresh-models` | Fetch model list from provider |
| POST | `/api/settings/test-prompt` | Test a prompt with the LLM (streaming) |
| POST | `/api/settings/model-info` | Get model details |
| PUT | `/api/settings/features` | Toggle feature flag |
| PUT | `/api/settings/system-prompt` | Update system prompt |
| PUT | `/api/settings/intelligent-search` | Toggle intelligent search |
| PUT | `/api/settings/search-summary-prompt` | Update search summary prompt |
| PUT | `/api/settings/retrieval` | Update retrieval settings |

### MCP Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings/mcp` | Get all MCP tool configurations |
| GET | `/api/settings/mcp/{tool}` | Get config for a specific MCP tool |
| PATCH | `/api/settings/mcp` | Update MCP tool configuration |

### Database Maintenance

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings/database-stats` | Stats for all databases |
| POST | `/api/settings/database/clear-chats` | Clear chat history |
| POST | `/api/settings/database/clear-searches` | Clear search history |
| POST | `/api/settings/database/clear-vectors` | Clear vector DB and file tracking |
| POST | `/api/settings/database/compact-chats` | Compact chat database |
| POST | `/api/settings/database/compact-searches` | Compact search database |

### Embeddings & Indexing

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings/embedding-models` | List embedding models + install status |
| GET | `/api/settings/embedding-models/status` | Poll background reindex progress |
| POST | `/api/settings/embedding-models/install` | Download an embedding model |
| PUT | `/api/settings/embedding-models/switch` | Switch model + background reindex |
| POST | `/api/index` | Trigger indexing |
| POST | `/api/index/cancel` | Cancel running index |

### Export

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/export` | Export conversations as markdown or JSON |

### Tags (requires `mcp_tag_generator` feature flag)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/tags/generate` | Generate AI tags for a markdown file |
| POST | `/api/tags/apply` | Apply tags to a file's frontmatter |
| POST | `/api/tags/bulk` | Bulk-tag files in a directory |

## Project Structure

```
app/
├── main.py              # Entry point, async lifespan, static serving, SPA catch-all
├── api.py               # App factory (create_app), CORS, router registration
├── config.py            # Settings singleton from YAML
├── schemas.py           # Pydantic request/response models
├── deps.py              # FastAPI Depends() functions for dependency injection
├── utils.py             # Shared helpers (SSE formatting, title generation)
├── ratelimit.py         # slowapi limiter + rate limit tiers
├── routers/             # API endpoint modules
│   ├── health.py        # Health checks, stats
│   ├── search.py        # Search, history, query enhancement
│   ├── chat.py          # RAG chat (sync + streaming)
│   ├── threads.py       # Thread listing, messages, rename, delete
│   ├── files.py         # File listing, indexing, RAG toggle
│   ├── settings.py      # Provider config, features, database maintenance
│   ├── embeddings.py    # Embedding model management, indexing
│   ├── export.py        # Conversation export
│   └── tags.py          # AI tag generation (conditional)
├── services/
│   ├── chat_service.py  # Conversation memory, streaming RAG, think-block stripping
│   ├── llm_service.py   # Ollama model discovery, connection testing
│   └── query_service.py # LLM-powered query enhancement
├── ingestion/           # File scanning, parsing, watching, indexing
├── embeddings/          # ONNX embedding (3 models, no PyTorch)
├── storage/             # ChromaDB vector store + SQLite (file tracking, chat, search)
├── rag/                 # LLM calls (LiteLLM), retrieval, prompts
├── mcp/                 # Filesystem + terminal + tag generator tools (optional)
├── planner/             # MCTS planning engine (optional)
└── skills/              # Agent skills for plan review (optional)

frontend/
├── src/
│   ├── App.tsx          # Tab layout (Chat, Search, Browse, Settings)
│   ├── lib/             # api.ts, sse.ts, types.ts, query-enhancement.ts
│   ├── hooks/           # use-chat, use-search, use-files, use-settings, use-llm-status
│   └── components/      # chat/, search/, browse/, settings/, ui/ (shadcn)
├── index.css            # Centralized styles
└── vite.config.ts       # Proxy /api -> backend in dev

config/
├── settings.yaml.example  # Configuration template (copy to settings.yaml)
└── mcp/                   # MCP tool configs (filesystem, terminal, tag_generator)

tests/                   # pytest + httpx AsyncClient

Makefile                 # Build, run, test, Docker targets (make help)
Dockerfile               # Multi-stage build (Node + Python), non-root, health check
docker-compose.yml       # Localhost-only binding, configurable source mounts
```
