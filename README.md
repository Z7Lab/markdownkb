# mdkb — Markdown Knowledge Base

A personal knowledge management system. Index your markdown files, search them semantically, and chat with your knowledge base using any LLM.

## Quick Start (Local)

```bash
# Install
./setup.sh

# Activate the environment
source .venv/bin/activate

# Run
python -m app
```

Open `http://localhost:9713` in your browser.

## Quick Start (Docker)

```bash
docker compose up --build
```

Open `http://localhost:9713` in your browser.

## Setup

### Local Development

```bash
# First time — creates .venv and installs everything
./setup.sh

# Activate the venv (needed every new terminal)
source .venv/bin/activate

# Run mdkb
python -m app
```

**Reinstall from scratch** (if deps break or you want a clean slate):
```bash
./setup.sh clean && ./setup.sh
```

**Just remove the venv:**
```bash
./setup.sh clean
```

### Docker

Edit `docker-compose.yml` to mount your markdown directories:

```yaml
volumes:
  - ./data:/app/data
  - ./config:/app/config
  - ./skills:/app/skills
  # Add your markdown folders here (read-only):
  - /home/user/notes:/app/docs/notes:ro
  - /home/user/documents:/app/docs/downloads:ro
```

Set your LLM API keys via environment variables:

```bash
export ANTHROPIC_API_KEY=sk-ant-PLACEHOLDER
# or
export OPENAI_API_KEY=sk-...
# or
export OLLAMA_API_BASE=http://<your-docker-host-ip>:11434
```

Then:
```bash
docker compose up --build
```

## Configuration

Edit `config/settings.yaml` or use the **Settings** tab in the UI. The YAML file has inline comments explaining every option. Here's a reference:

### Sources

| Key | Default | Description |
|-----|---------|-------------|
| `sources` | `[./docs]` | Directories to scan for markdown files. Relative paths resolve from project root. |
| `global_ignore` | node_modules, .git, etc. | Glob patterns to skip during scanning. |

### Embeddings

| Key | Default | Description |
|-----|---------|-------------|
| `embeddings.model` | `all-MiniLM-L6-v2` | Embedding model. Uses ChromaDB's built-in ONNX runtime (no PyTorch). |
| `embeddings.chunk_size` | `512` | Max characters per chunk when splitting documents. |
| `embeddings.chunk_overlap` | `50` | Character overlap between consecutive chunks. |

Embedding uses ONNX and defaults to half your CPU cores to avoid locking up your system. Override with:

```bash
OMP_NUM_THREADS=2 python -m app    # use only 2 cores
```

Indexing processes chunks in batches of 500 and saves each batch to disk, so partial progress survives crashes.

### LLM Providers

| Key | Default | Description |
|-----|---------|-------------|
| `llm.providers` | anthropic, openai, ollama | List of LLM backends. Each has `name`, `model`, `api_key`, `api_base`. |
| `llm.active_provider` | `ollama` | Which provider to use. Must match a provider `name`. |
| `llm.temperature` | `0.3` | Response randomness (0.0 = deterministic, 1.0 = creative). |
| `llm.max_tokens` | `2048` | Max response length from the LLM. |

Model names use [litellm format](https://docs.litellm.ai/docs/providers): `provider/model` (e.g. `ollama/qwen3:32b`, `anthropic/claude-3-5-sonnet-20241022`).

Providers without an `api_key` are skipped automatically (except ollama, which doesn't need one). If the active provider fails, others are tried as fallbacks.

### Retrieval

| Key | Default | Description |
|-----|---------|-------------|
| `retrieval.top_k` | `5` | Number of document chunks to retrieve per query. |
| `retrieval.score_threshold` | `0.1` | Minimum cosine similarity score (0-1) to include a result. MiniLM scores for relevant matches are typically 0.15-0.45. Lower = more inclusive. |
| `retrieval.hybrid_search` | `true` | Combine vector search with BM25 keyword matching for better results. |
| `retrieval.bm25_weight` | `0.3` | Keyword vs. vector balance (0.0 = pure vector, 1.0 = pure keyword). |

### Storage

| Key | Default | Description |
|-----|---------|-------------|
| `storage.persist_directory` | `./data/chromadb` | Where the vector index is stored on disk. |
| `storage.collection_name` | `mdkb` | ChromaDB collection name. |

### Features

| Key | Default | Description |
|-----|---------|-------------|
| `features.rag_chat` | `true` | Main chat interface with RAG. |
| `features.file_watcher` | `true` | Auto-reindex when files change on disk. |
| `features.mcp_filesystem` | `false` | MCP file browsing tool. |
| `features.mcp_terminal` | `false` | MCP terminal command tool. |
| `features.mcts_planner` | `false` | MCTS-based plan generation. |
| `features.agent_skills` | `false` | Agent skill system for plan review. |

### Server

| Key | Default | Description |
|-----|---------|-------------|
| `server.host` | `0.0.0.0` | Bind address (0.0.0.0 = all interfaces). |
| `server.port` | `9713` | Web UI and API port. |

## CLI

```bash
source .venv/bin/activate

# Index your markdown files
python -m app.cli index

# Search
python -m app.cli search "what did I write about authentication"

# Add a source directory
python -m app.cli add-source /path/to/your/notes

# Show stats
python -m app.cli stats
```

## LLM Setup

mdkb doesn't run LLMs locally — it calls them over the network.

**Anthropic / OpenAI:** Set your API key in `config/settings.yaml` or via environment variable.

**Ollama on another machine:** See [docs/ollama-remote-setup.md](docs/ollama-remote-setup.md).

Providers are tried in order — if one fails, mdkb falls back to the next.

## API

FastAPI endpoints are available alongside the UI at `http://localhost:9713/api/`:

- `GET /api/health` — health check
- `POST /api/search` — semantic search
- `POST /api/chat` — RAG chat
- `POST /api/index` — trigger re-index
- `GET /api/stats` — index statistics
- `GET /api/files` — list indexed files
- `GET /api/file?path=...` — read a file
- `POST /api/export` — export conversation history

## Project Structure

```
app/
├── main.py              # Gradio app + FastAPI mount
├── config.py            # Settings management
├── cli.py               # CLI commands
├── api.py               # REST API endpoints
├── ingestion/           # File scanning, parsing, watching
├── embeddings/          # ONNX embedding (all-MiniLM-L6-v2, no PyTorch)
├── storage/             # ChromaDB vector store
├── rag/                 # LLM calls, retrieval, prompts
├── ui/                  # Gradio chat + browser + settings
├── mcp/                 # Filesystem + terminal tools (optional)
├── planner/             # MCTS planning engine (optional)
└── skills/              # Agent Skills for plan review (optional)
```
