# Getting Started

This guide walks you through setting up mdkb, indexing your first documents, and running your first search and chat.

## Prerequisites

- **Docker** (recommended) or Python 3.11+
- **Markdown files** to index (project docs, notes, guides, etc.)
- **An LLM** — either Ollama running locally (free) or a cloud API key (Anthropic, OpenAI, Venice)

## 1. Install and Start

### Docker (recommended)

```bash
git clone <repo-url> && cd mdkb
cp config/settings.yaml.example config/settings.yaml
cp .env.example .env
make build && make up
```

Open http://localhost:9713. You should see the mdkb UI with a setup banner.

### Native

```bash
cp config/settings.yaml.example config/settings.yaml
./run.sh
```

Open http://localhost:5173 (dev mode) or http://localhost:9713 (production).

## 2. Configure Your LLM

mdkb needs an LLM for chat, search summaries, and entity extraction. You have three options:

### Option A: Ollama (free, local, private)

1. Install Ollama: https://ollama.com/download
2. Pull a model: `ollama pull qwen3:8b` (or any model you prefer)
3. In mdkb Settings > Chat Model, select the Ollama provider
4. Set API Base to `http://localhost:11434` (or your Ollama host)
5. Click "Refresh" to see available models, select one, and Save

See [Local LLM Setup](local-llm-setup.md) for detailed instructions.

### Option B: Cloud API (Anthropic, OpenAI, Venice)

1. Get an API key from your provider
2. Create a secrets file: `echo -n "your-key" > secrets/<provider>_api_key`
3. In mdkb Settings > Chat Model, select the provider and Save

### Option C: Any OpenAI-compatible server

llama.cpp, vLLM, LM Studio, or any server with an OpenAI-compatible API:

1. In mdkb Settings > Chat Model, set the API Base to your server URL (e.g. `http://localhost:8080/v1`)
2. Set the model ID as `openai/<model-name>`
3. Save

## 3. Add Your Documents

Edit `config/settings.yaml` and add your markdown directories under `sources:`:

```yaml
sources:
  - /path/to/your/docs
  - /path/to/another/folder
```

Restart the container (`make restart`) or use Settings > Sources in the UI. mdkb will auto-index all `.md` files.

## 4. Your First Search

Go to the **Search** tab and type a query. mdkb uses hybrid search — vector similarity + keyword matching. Results show relevant chunks with source file links and relevance scores.

Click any result to view the source file. Use the AI Summary button to get an LLM-synthesized answer.

## 5. Your First Chat

Go to the **Chat** tab and ask a question. mdkb retrieves relevant documents and generates an answer grounded in your knowledge base. The response includes source citations — click them to verify.

## 6. Connect Agents via MCP

mdkb exposes 32 MCP tools over stdio or SSE. Any MCP-compatible client can search, chat, and manage your knowledge base.

**Claude Desktop / Claude Code:**
Add mdkb as an MCP server pointing to `http://localhost:9715/sse` (SSE transport) or run `python mcp_server.py` (stdio).

See [MCP Server](../reference/mcp-server.md) for the full tool reference and setup instructions.

## What's Next

- **[Configuration](../reference/configuration.md)** — all settings, feature flags, secrets
- **[Embedding Models](embedding-models.md)** — choose and configure embedding models
- **[Architecture](../reference/architecture.md)** — how the system works
- **[Plugins](plugin-development.md)** — enable features and build your own
- **[API Reference](../reference/api.md)** — full endpoint listing
- **[Security](../../SECURITY.md)** — API key setup, network exposure, feature flags
