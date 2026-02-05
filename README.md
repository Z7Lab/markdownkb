# mdkb — Markdown Knowledge Base

A personal knowledge management system. Index your markdown files, search them semantically, and chat with your knowledge base using any LLM.

Python (FastAPI) backend + React (Vite + TypeScript + Shadcn/ui) frontend.

## Quick Start

```bash
./run.sh
```

That's it. Creates `.venv`, installs Python and Node dependencies if needed, starts both services. Open `http://localhost:9714` (dev) or `http://localhost:9713` (production).

## run.sh

```bash
./run.sh           # dev mode (default): hot reload, backend:9713 + frontend:9714
./run.sh -p        # production: builds frontend, serves everything on :9713
./run.sh -b        # backend only, no frontend
./run.sh -h        # help
```

- Auto-creates `.venv` and installs `requirements.txt` if missing
- Auto-installs `frontend/node_modules` if missing
- Kills existing processes on ports before starting
- Ctrl+C kills everything
- Health checks both services with color-coded status
- Reads `.env` for port overrides (copy `.env.example` to `.env`)

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
| `retrieval.score_threshold` | `0.1` | Minimum similarity score |
| `retrieval.hybrid_search` | `true` | Combine vector + BM25 keyword search |
| `retrieval.bm25_weight` | `0.3` | Keyword vs vector balance |

### Features

| Key | Default | Description |
|-----|---------|-------------|
| `features.rag_chat` | `true` | Chat with RAG |
| `features.file_watcher` | `true` | Auto-reindex on file changes |
| `features.mcp_filesystem` | `false` | MCP file browsing tool |
| `features.mcp_terminal` | `false` | MCP terminal tool |
| `features.mcts_planner` | `false` | MCTS plan generation |
| `features.agent_skills` | `false` | Agent skill system |

## LLM Setup

mdkb calls LLMs over the network — it doesn't run them locally.

**Anthropic / OpenAI:** Set your API key in `config/settings.yaml` or via environment variable (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).

**Ollama on another machine:** See [docs/ollama-remote-setup.md](docs/ollama-remote-setup.md).

## API

All endpoints at `http://localhost:9713/api/`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/stats` | Index statistics |
| POST | `/api/search` | Semantic search |
| POST | `/api/chat` | RAG chat (non-streaming) |
| POST | `/api/chat/stream` | SSE streaming chat |
| DELETE | `/api/chat/history` | Clear conversation |
| POST | `/api/chat/save-plan` | Save response as markdown |
| GET | `/api/files` | List indexed files |
| GET | `/api/file?path=...` | Read file content |
| POST | `/api/files/exclude` | Exclude file from RAG |
| POST | `/api/files/include` | Re-include file in RAG |
| GET | `/api/sources` | List source directories |
| POST | `/api/sources` | Add source directory |
| DELETE | `/api/sources` | Remove source directory |
| GET | `/api/settings` | Get full settings |
| PUT | `/api/settings/provider` | Save LLM provider config |
| POST | `/api/settings/test-connection` | Test LLM connectivity |
| POST | `/api/settings/refresh-models` | Fetch Ollama model list |
| PUT | `/api/settings/features` | Toggle feature flag |
| POST | `/api/index` | Trigger re-index |
| POST | `/api/index/cancel` | Cancel running index |
| POST | `/api/export` | Export conversation history |
| GET | `/api/folders` | List unique folders |
| GET | `/api/tags` | List unique tags |

## Project Structure

```
app/
├── main.py              # Entry point, static serving, SPA catch-all
├── config.py            # Settings from YAML
├── api.py               # All FastAPI endpoints (REST + SSE)
├── services/
│   ├── chat_service.py  # Conversation memory, streaming RAG, think-block stripping
│   └── llm_service.py   # Ollama model discovery, connection testing
├── ingestion/           # File scanning, parsing, watching, indexing
├── embeddings/          # ONNX embedding (all-MiniLM-L6-v2, no PyTorch)
├── storage/             # ChromaDB vector store + SQLite file tracking
├── rag/                 # LLM calls (LiteLLM), retrieval, prompts
├── mcp/                 # Filesystem + terminal tools (optional)
├── planner/             # MCTS planning engine (optional)
└── skills/              # Agent skills for plan review (optional)

frontend/
├── src/
│   ├── App.tsx          # Tab layout (Chat, Search, Browse, Settings)
│   ├── lib/             # api.ts, sse.ts, types.ts
│   ├── hooks/           # use-chat, use-search, use-files, use-settings
│   └── components/      # chat/, search/, browse/, settings/, ui/ (shadcn)
├── index.css            # Centralized styles
└── vite.config.ts       # Proxy /api -> backend in dev
```
