# MarkdownKB — Markdown Knowledge Base

**Search-first documentation exploration for your markdown knowledge base.**

Combines semantic vector search with keyword matching (hybrid BM25+vector), tracks search history with versioning, and lets you explore findings through conversational AI. Purpose-built for documentation, not general chat.

Python (FastAPI) backend + React (Vite + TypeScript + Shadcn/ui) frontend.

## Quick Start

```bash
git clone https://github.com/Z7Lab/markdownkb
cd markdownkb
```

### Option A: Docker (recommended)

1. **Copy config files** (first time only):
   ```bash
   cp config/settings.yaml.example config/settings.yaml
   cp .env.example .env
   ```

2. **(Optional) Seed `config/settings.yaml`** — this file is read **once on first boot** to seed the settings database, then never read again. You can pre-seed source directories (under `sources:`) and an LLM provider here, or skip it and configure everything from the **Settings** tab after the app starts. Runtime config lives in the settings database (`markdownkb_settings.db`), not this file.

3. **Add API keys** (if using cloud providers) — create secret files:
   ```bash
   echo -n "your-key" > secrets/venice_api_key    # or anthropic_api_key, openai_api_key
   ```
   Run `make secrets-init` on a fresh clone to create `secrets/` and empty placeholder files.

4. **Edit `.env`** (optional) — defaults work out of the box. Uncomment and set values only if you need to:
   - `OLLAMA_API_BASE` — if Ollama runs on a different machine
   - `MARKDOWNKB_HOST=0.0.0.0` — to access from other machines via `http://<hostname>.local:9713` (localhost only by default)
   - `MARKDOWNKB_API_KEY` — set a key to protect the API (recommended if exposing to the network)

5. **Build and start**:
   ```bash
   make docker-build && make docker-up
   ```

Source directories are mounted individually into the container — `compose.override.yml` is auto-generated from your `settings.yaml` sources when you add or remove directories via the UI. Copy the example on first setup: `cp compose.override.yml.example compose.override.yml`. After adding sources, restart: `make docker-down && make docker-up`. The container binds to **localhost only** by default and runs as a non-root user.

### Option B: Native

```bash
cp config/settings.yaml.example config/settings.yaml  # first time only
./run.sh
```

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

## Makefile

```bash
make help              # show all targets
make dev               # alias for ./run.sh
make docker-build      # build image (cached layers — use docker-rebuild after source changes)
make docker-rebuild    # clean rebuild (no cache) + restart — use after code or dependency changes
make docker-up         # start container (detached)
make docker-down       # stop container
make docker-logs       # tail container logs
make docker-shell      # open a shell in the container
make docker-restart    # restart container
make docker-clean      # stop container and remove image (preserves data volumes)
make docker-clean-all  # stop container, remove image AND data volumes (destructive)
```

**After changing config (Docker):**

| What changed | What to run |
|---|---|
| `.env` (ports, bind address) | `make docker-down && make docker-up` |
| Settings (sources, LLM, features) | Nothing — change them in the **Settings** tab; they save to the DB and apply live |
| `config/settings.yaml` | Only read on first boot to seed the DB; editing it later has no effect (delete the DB to re-seed) |
| Code or dependencies | `make docker-rebuild` |

## Configuration

Configure via the **Settings** tab in the UI — changes save to the settings database and apply live. `config/settings.yaml` is a one-time seed read on first boot (when the DB is empty), not the live config surface. See [docs/reference/configuration.md](docs/reference/configuration.md) for the full reference (all settings, feature flags, `.env` vs seed precedence).

**Advanced — symlink pattern:** If you manage multiple machines or want configs and secrets centrally backed up outside the repo, move `.env`, `config/settings.yaml`, and the `secrets/` directory to a gitignored location outside the project and symlink them back. Most users don't need this — plain files work fine.

## LLM Setup

MarkdownKB calls LLMs over the network — it doesn't run them locally.

**Anthropic / OpenAI / Venice:** Add your API key to `secrets/<provider>_api_key` (run `make secrets-init` to scaffold the directory) or set the `<PROVIDER>_API_KEY` environment variable.

**Ollama on another machine:** See [docs/thirdparty/ollama-remote-setup.md](docs/thirdparty/ollama-remote-setup.md).

## API

Interactive docs (Swagger UI) at `http://localhost:9713/docs` — always up to date.

See [docs/reference/api.md](docs/reference/api.md) for the full endpoint reference.

## CLI

MarkdownKB includes a command-line interface that wraps the REST API so you can search, chat, manage sources, and work with buckets without the web UI.

```bash
# Quick checks
markdownkb health
markdownkb stats

# Search and chat
markdownkb search "authentication flow" --top-k 5
markdownkb chat "How does the auth system work?"

# Sources
markdownkb sources list
markdownkb sources add /home/user/docs
markdownkb sources remove /home/user/old-docs --cleanup

# Buckets
markdownkb buckets list
markdownkb buckets create research --source /tmp/papers --expires-in 86400
markdownkb buckets search research "key findings"
markdownkb buckets delete research

# Force re-index
markdownkb index --force

# Machine-readable output (any command)
markdownkb search "query" --json | jq '.results[] | .metadata.source_path'
```

Configure the target instance via `~/.markdownkb` (YAML):

```yaml
url: http://my-server.local:9713
api_key: your-key-here
```

Or via environment variables `MARKDOWNKB_URL` and `MARKDOWNKB_API_KEY`. Every command also accepts `--url` and `--api-key` flags. See [docs/reference/cli.md](docs/reference/cli.md) for the full reference.

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/how-to/getting-started.md) | Install, configure, first search and chat |
| [Local LLM Setup](docs/how-to/local-llm-setup.md) | Step-by-step Ollama install and model setup |
| [API Key Setup](docs/how-to/api-key-setup.md) | When you need a key, how to set one |
| [Configuration](docs/reference/configuration.md) | All settings, feature flags, `.env` vs `settings.yaml` |
| [API Reference](docs/reference/api.md) | Full endpoint listing |
| [MCP Server](docs/reference/mcp-server.md) | 35 MCP tools, transports, authentication |
| [Architecture](docs/reference/architecture.md) | System overview, data flow, storage, plugins |
| [Embedding Models](docs/how-to/embedding-models.md) | Local ONNX and remote embedding (Ollama, cloud) |
| [Knowledge Graph](docs/explanation/knowledge-graph.md) | Entity extraction and document similarity |
| [Security](SECURITY.md) | Threat model, feature flags, vulnerability reporting |
| [All Documentation](docs/README.md) | Full documentation index (Diataxis) |

## Project Structure

```
app/
├── main.py              # Entry point, async lifespan, static serving, SPA catch-all
├── api.py               # App factory (create_app), CORS, router + plugin registration
├── auth.py              # API key middleware (X-MarkdownKB-Key header)
├── config/              # Settings package (DB-backed; settings.yaml seeds it on first boot)
├── schemas.py           # Pydantic request/response models
├── deps.py              # FastAPI Depends() functions for dependency injection
├── utils.py             # Shared helpers (SSE formatting, title generation)
├── logbuffer.py         # In-memory ring buffer log handler for UI log viewer
├── ratelimit.py         # slowapi limiter + rate limit tiers
├── cli.py               # CLI commands (index, search, add-source, stats)
├── routers/             # Core API endpoint modules (always registered)
│   ├── health.py        # Health checks, stats
│   ├── chat.py          # RAG chat (sync + streaming)
│   ├── threads.py       # Thread listing, messages, rename, delete
│   ├── files.py         # File listing, indexing, RAG toggle
│   ├── sources.py       # Source directories + project roots
│   ├── settings.py      # Core/MCP flags, prompts, retrieval tuning
│   ├── llm.py           # LLM provider config, discovery, testing
│   ├── embeddings.py    # Embedding model management, indexing
│   ├── scopes.py        # Scope CRUD
│   ├── plugins.py       # Plugin enable/disable + per-plugin config
│   ├── mcp.py           # MCP tool flags + config
│   ├── setup.py         # First-run setup, API key generation
│   ├── dashboard.py     # Home dashboard stats + widgets
│   ├── maintenance.py   # Database maintenance, reindex
│   ├── tasks.py         # Background task registry status
│   └── export_md.py     # Conversation export
├── plugins/             # Auto-discovered, enabled via plugins.<name>.enabled
│   ├── search/          # Semantic search, history, deep research
│   ├── converter/       # Document + audio → markdown, Import-tab ingestion
│   ├── buckets/         # Temporary scoped document collections
│   ├── docmap/          # 3D document-similarity visualization
│   ├── knowledge_graph/ # Entity/relationship extraction + graph
│   ├── wiki_compile/    # LLM-synthesized wiki pages
│   ├── lint/            # Tiered knowledge-base health check
│   ├── planner/         # MCTS plan generation
│   ├── tags/            # Tag storage, CRUD, AI tag generation
│   ├── catalogs/        # Model catalog providers (Ollama, Venice)
│   ├── export/          # Chat conversation export
│   └── write_api/       # Document creation via HTTP
├── services/
│   ├── chat_service.py    # Conversation memory, streaming RAG, think-block stripping
│   ├── llm_service.py     # Ollama model discovery, connection testing
│   ├── query_service.py   # LLM-powered query enhancement
│   ├── kg_extraction.py   # LLM-based entity/relationship extraction
│   ├── graph_service.py   # Knowledge-graph queries (entities, paths)
│   ├── scope_service.py   # Scope resolution for retrieval
│   ├── settings_service.py # Builds the GET /settings response
│   ├── task_registry.py   # Shared background-task registry
│   ├── planner_service.py # MCTS planner orchestration + skill reviews
│   └── deep_research.py   # MCTS-powered multi-angle research synthesis
├── ingestion/           # File scanning, parsing, watching, indexing
├── embeddings/          # ONNX embedding (3 models, no PyTorch)
├── storage/             # ChromaDB vector store + SQLite (tracking, chat, search, KG)
├── rag/                 # LLM calls (Anthropic/OpenAI SDKs), retrieval, prompts
├── mcp/                 # MCP server tool modules (tools/) + history tracking
├── planner/             # MCTS planning engine (optional)
└── skills/              # Agent skills for plan review (optional)

mcp_server.py            # Standalone MCP server (stdio/Streamable HTTP, separate process)

frontend/
├── src/
│   ├── App.tsx          # Tab layout (Home, Chat, Search, Planner, Doc Map, Knowledge Graph, Buckets, Wiki, Import, Files, Settings)
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

## License

MIT — see [LICENSE](LICENSE).

