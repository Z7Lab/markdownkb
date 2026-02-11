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

```bash
cp config/settings.yaml.example config/settings.yaml  # add your source dirs and LLM config
cp .env.example .env                                   # edit if needed (ports, Ollama IP, API keys)
make build && make up
```

Your home directory is mounted read-only into the container, so paths in `settings.yaml` work identically. The container binds to **localhost only** by default and runs as a non-root user.

Edit `config/settings.yaml` to add your source directories and LLM API keys. The example file has sensible defaults for everything else.

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

## Configuration

Edit `config/settings.yaml` or use the **Settings** tab in the UI. See [docs/configuration.md](docs/configuration.md) for the full reference (all settings, feature flags, `.env` vs `settings.yaml` precedence).

## LLM Setup

mdkb calls LLMs over the network — it doesn't run them locally.

**Anthropic / OpenAI:** Set your API key in `config/settings.yaml` or via environment variable (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).

**Ollama on another machine:** See [docs/ollama-remote-setup.md](docs/ollama-remote-setup.md).

## API

Interactive docs (Swagger UI) at `http://localhost:9713/docs` — always up to date.

See [docs/api.md](docs/api.md) for the full endpoint reference.

## CLI

mdkb includes a command-line interface for indexing and search without starting the web server. See [docs/cli.md](docs/cli.md).

## Documentation

| Document | Description |
|----------|-------------|
| [Configuration](docs/configuration.md) | All settings, feature flags, `.env` vs `settings.yaml` |
| [API Reference](docs/api.md) | Full endpoint listing |
| [Architecture](docs/architecture.md) | System overview, data flow, storage, pipelines |
| [CLI](docs/cli.md) | Command-line interface |
| [Embedding Models](docs/embedding-models.md) | Available models, switching, storage |
| [Ollama Remote Setup](docs/ollama-remote-setup.md) | Running Ollama on a separate machine |
| [MCP Tools](docs/mcp-tools.md) | File browsing, terminal, AI tag generation |
| [Security](SECURITY.md) | Threat model, feature flags, vulnerability reporting |

## Project Structure

```
app/
├── main.py              # Entry point, async lifespan, static serving, SPA catch-all
├── api.py               # App factory (create_app), CORS, router registration
├── config.py            # Settings singleton from YAML
├── schemas.py           # Pydantic request/response models
├── deps.py              # FastAPI Depends() functions for dependency injection
├── utils.py             # Shared helpers (SSE formatting, title generation)
├── logbuffer.py         # In-memory ring buffer log handler for UI log viewer
├── ratelimit.py         # slowapi limiter + rate limit tiers
├── cli.py               # CLI commands (index, search, add-source, stats)
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
│   ├── contexts/        # React contexts (navigation)
│   ├── hooks/           # use-chat, use-search, use-files, use-settings, + more
│   └── components/      # chat/, search/, browse/, settings/, ui/ (shadcn)
├── index.css            # Centralized styles
└── vite.config.ts       # Proxy /api -> backend in dev

config/
└── settings.yaml.example  # Configuration template (copy to settings.yaml)

tests/                   # pytest + httpx AsyncClient

Makefile                 # Build, run, test, Docker targets (make help)
Dockerfile               # Multi-stage build (Node + Python), non-root, health check
docker-compose.yml       # Localhost-only binding, configurable source mounts
```
