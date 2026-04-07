# mdkb — Markdown Knowledge Base

**Search-first documentation exploration for your markdown knowledge base.**

Combines semantic vector search with keyword matching (hybrid BM25+vector), tracks search history with versioning, and lets you explore findings through conversational AI. Purpose-built for documentation, not general chat.

Python (FastAPI) backend + React (Vite + TypeScript + Shadcn/ui) frontend.

## Quick Start

### Option A: Native

```bash
cp config/settings.yaml.example config/settings.yaml  # first time only
./run.sh
```

Creates `.venv`, installs Python and Node dependencies if needed, starts both services. Open `http://localhost:5173` (dev) or `http://localhost:9713` (production).

### Option B: Docker

1. **Copy config files** (first time only):
   ```bash
   cp config/settings.yaml.example config/settings.yaml
   cp .env.example .env
   ```

2. **Edit `config/settings.yaml`** — add your source directories under `sources:` and configure your LLM provider. Everything else has sensible defaults.

3. **Add API keys** (if using cloud providers) — create secret files:
   ```bash
   echo -n "your-key" > secrets/venice_api_key    # or anthropic_api_key, openai_api_key
   ```
   See `secrets/README.md` for details.

4. **Edit `.env`** (optional) — defaults work out of the box. Uncomment and set values only if you need to:
   - `OLLAMA_API_BASE` — if Ollama runs on a different machine
   - `MDKB_HOST=0.0.0.0` — to access from other machines via `http://<hostname>.local:9713` (localhost only by default)
   - `MDKB_API_KEY` — set a key to protect the API (recommended if exposing to the network)

5. **Build and start**:
   ```bash
   make build && make up
   ```

Your home directory is mounted read-only into the container, so paths in `settings.yaml` work identically. The container binds to **localhost only** by default and runs as a non-root user. The Makefile reads `.env` automatically — no extra steps needed.

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

## Makefile

```bash
make help       # show all targets
make dev        # alias for ./run.sh
make build      # build Docker image
make up         # start container (detached)
make down       # stop container
make logs       # tail container logs
make shell      # open a shell in the container
make restart    # restart container
make clean      # stop container and remove image
```

**After changing config (Docker):**

| What changed | What to run |
|---|---|
| `.env` (ports, API keys, bind address) | `make down && make up` |
| `config/settings.yaml` (sources, LLM, features) | `make restart` |
| Code or dependencies | `make build && make up` |

## Configuration

Edit `config/settings.yaml` or use the **Settings** tab in the UI. See [docs/configuration.md](docs/configuration.md) for the full reference (all settings, feature flags, `.env` vs `settings.yaml` precedence).

## LLM Setup

mdkb calls LLMs over the network — it doesn't run them locally.

**Anthropic / OpenAI / Venice:** Add your API key to `secrets/<provider>_api_key` (see `secrets/README.md`) or set the `<PROVIDER>_API_KEY` environment variable.

**Ollama on another machine:** See [docs/ollama-remote-setup.md](docs/ollama-remote-setup.md).

## API

Interactive docs (Swagger UI) at `http://localhost:9713/docs` — always up to date.

See [docs/api.md](docs/api.md) for the full endpoint reference.

## CLI

mdkb includes a command-line interface for indexing and search without starting the web server. See [docs/cli.md](docs/cli.md).

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | Install, configure, first search and chat |
| [Local LLM Setup](docs/local-llm-setup.md) | Step-by-step Ollama install and model setup |
| [API Key Setup](docs/api-key-setup.md) | When you need a key, how to set one |
| [Configuration](docs/configuration.md) | All settings, feature flags, `.env` vs `settings.yaml` |
| [API Reference](docs/api.md) | Full endpoint listing |
| [MCP Server](docs/mcp-server.md) | 32 MCP tools, transports, authentication |
| [Architecture](docs/architecture.md) | System overview, data flow, storage, plugins |
| [Embedding Models](docs/embedding-models.md) | Local ONNX and remote embedding (Ollama, cloud) |
| [Knowledge Graph](docs/knowledge-graph.md) | Entity extraction and document similarity |
| [Security](SECURITY.md) | Threat model, feature flags, vulnerability reporting |
| [All Documentation](docs/README.md) | Full documentation index |

## Project Structure

```
app/
├── main.py              # Entry point, async lifespan, static serving, SPA catch-all
├── api.py               # App factory (create_app), CORS, router + plugin registration
├── auth.py              # API key middleware (X-MDKB-Key header)
├── config.py            # Settings singleton from YAML
├── schemas.py           # Pydantic request/response models
├── deps.py              # FastAPI Depends() functions for dependency injection
├── utils.py             # Shared helpers (SSE formatting, title generation)
├── logbuffer.py         # In-memory ring buffer log handler for UI log viewer
├── ratelimit.py         # slowapi limiter + rate limit tiers
├── cli.py               # CLI commands (index, search, add-source, stats)
├── routers/             # Core API endpoint modules (always registered)
│   ├── health.py        # Health checks, stats
│   ├── search.py        # Search, history, query enhancement
│   ├── chat.py          # RAG chat (sync + streaming)
│   ├── threads.py       # Thread listing, messages, rename, delete
│   ├── files.py         # File listing, indexing, RAG toggle
│   ├── settings.py      # Provider config, features, database maintenance
│   ├── embeddings.py    # Embedding model management, indexing
│   └── export.py        # Conversation export
├── plugins/             # Auto-discovered, enabled via plugins.<name>.enabled
│   ├── planner/         # MCTS plan generation
│   ├── tags/            # Tag storage, CRUD, AI tag generation
│   └── write_api/       # Document creation via HTTP
├── services/
│   ├── chat_service.py  # Conversation memory, streaming RAG, think-block stripping
│   ├── llm_service.py   # Ollama model discovery, connection testing
│   ├── query_service.py # LLM-powered query enhancement
│   ├── kg_extraction.py # LLM-based entity/relationship extraction for knowledge graph
│   ├── planner_service.py # MCTS planner orchestration + skill reviews
│   └── deep_research.py # MCTS-powered multi-angle research synthesis
├── ingestion/           # File scanning, parsing, watching, indexing
├── embeddings/          # ONNX embedding (3 models, no PyTorch)
├── storage/             # ChromaDB vector store + SQLite (tracking, chat, search, KG)
├── rag/                 # LLM calls (Anthropic/OpenAI SDKs), retrieval, prompts
├── mcp/                 # MCP server tool modules (tools/) + history tracking
├── planner/             # MCTS planning engine (optional)
└── skills/              # Agent skills for plan review (optional)

mcp_server.py            # Standalone MCP server (stdio/SSE, separate process)

frontend/
├── src/
│   ├── App.tsx          # Tab layout (Chat, Search, Planner, Browse, Settings)
│   ├── lib/             # api.ts, sse.ts, types.ts, query-enhancement.ts
│   ├── contexts/        # React contexts (navigation)
│   ├── hooks/           # use-chat, use-search, use-planner, use-files, use-settings, + more
│   └── components/      # chat/, search/, planner/, browse/, settings/, ui/ (shadcn)
├── index.css            # Centralized styles
└── vite.config.ts       # Proxy /api -> backend in dev

config/
└── settings.yaml.example  # Configuration template (copy to settings.yaml)

tests/                   # pytest + httpx AsyncClient

Makefile                 # Build, run, test, Docker targets (make help)
Dockerfile               # Multi-stage build (Node + Python), non-root, health check
compose.yml              # Localhost-only binding, configurable source mounts
```
