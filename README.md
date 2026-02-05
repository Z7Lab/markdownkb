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

Edit `config/settings.yaml` to configure:

- **sources** — directories to index for markdown files
- **llm.providers** — LLM backends (Anthropic, OpenAI, Ollama, etc.)
- **llm.active_provider** — which provider to use
- **features** — toggle optional features (file watcher, MCP, MCTS planner, etc.)

You can also configure sources and LLM provider from the **Settings** tab in the UI.

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

## Port

mdkb runs on port **9713** by default. Change it in `config/settings.yaml`:

```yaml
server:
  port: 9713
```

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
