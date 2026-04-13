# Getting Started

This guide walks you through setting up MarkdownKB, indexing your first documents, and running your first search and chat.

## Prerequisites

- **Docker** (recommended) or Python 3.11+
- **Markdown files** to index (project docs, notes, guides, etc.)
- **An LLM** — either Ollama running locally (free) or a cloud API key (Anthropic, OpenAI, Venice)

## 1. Install and Start

### Docker (recommended)

```bash
git clone <repo-url> && cd markdownkb
cp config/settings.yaml.example config/settings.yaml
cp .env.example .env
make docker-build && make docker-up
```

After any code or dependency change — including pulling updates or switching branches — use `make docker-rebuild`. It bypasses Docker's layer cache and restarts the container. `make docker-build` is only safe when you haven't changed source; its layer cache can occasionally miss frontend changes silently.

Open http://localhost:9713. You should see the MarkdownKB UI with a setup banner.

### Native

```bash
cp config/settings.yaml.example config/settings.yaml
./run.sh
```

Open http://localhost:5173 (dev mode) or http://localhost:9713 (production).

## 2. Configure Your LLM

MarkdownKB needs an LLM for chat, search summaries, and entity extraction. You have three options:

### Option A: Ollama (free, local, private)

1. Install Ollama: https://ollama.com/download
2. Pull a model: `ollama pull qwen3:8b` (or any model you prefer)
3. In MarkdownKB Settings > Chat Model, select the Ollama provider
4. Set API Base to `http://localhost:11434` (or your Ollama host)
5. Click "Refresh" to see available models, select one, and Save

See [Local LLM Setup](local-llm-setup.md) for detailed instructions.

### Option B: Cloud API (Anthropic, OpenAI, Venice)

1. Get an API key from your provider
2. Create a secrets file: `echo -n "your-key" > secrets/<provider>_api_key`
3. In MarkdownKB Settings > Chat Model, select the provider and Save

### Option C: Any OpenAI-compatible server

llama.cpp, vLLM, LM Studio, or any server with an OpenAI-compatible API:

1. In MarkdownKB Settings > Chat Model, set the API Base to your server URL (e.g. `http://localhost:8080/v1`)
2. Set the model ID as `openai/<model-name>`
3. Save

## 3. Add Your Documents

Go to **Settings → Sources** in the UI and add directories under **Watch Directories**. MarkdownKB will immediately start indexing all `.md` files it finds.

Alternatively, edit `config/settings.yaml` directly and add directories under `sources:`:

```yaml
sources:
  - path: /path/to/your/docs
  - path: /path/to/another/folder
```

Each source has a `path` and an optional `writable` flag (defaults to `true`). Set `writable: false` to prevent the Write API and MCP tools from modifying files in that directory.

In Docker, newly added source paths must be mounted into the container. MarkdownKB updates `config/compose.override.yml` automatically when you add a source via the UI, and also regenerates it on every startup. Restart the container after adding a source to apply the new mount: `make docker-restart`.

### Indexing a project directory

If your documents live across many repositories, use **Project Directories** instead of adding each repo individually. Point MarkdownKB at a parent directory containing cloned repos and it will discover and index matching docs in each subdirectory automatically.

In **Settings → Sources → Project Directories**, click **Add**, enter the path (e.g. `/home/user/projects`), and configure include/exclude patterns. New repos cloned into that directory are picked up automatically within ~60 seconds.

In Docker, the project directory path must also be mounted — MarkdownKB adds it to `config/compose.override.yml` when you save, then restart: `make docker-restart`.

## 4. Your First Search

Go to the **Search** tab and type a query. MarkdownKB uses hybrid search — vector similarity + keyword matching. Results show relevant chunks with source file links and relevance scores.

Click any result to view the source file. Use the AI Summary button to get an LLM-synthesized answer.

## 5. Your First Chat

Go to the **Chat** tab and ask a question. MarkdownKB retrieves relevant documents and generates an answer grounded in your knowledge base. The response includes source citations — click them to verify.

## 6. Connect Agents via MCP

MarkdownKB exposes 32 MCP tools over stdio or Streamable HTTP. Any MCP-compatible client can search, chat, and manage your knowledge base.

**Claude Desktop / Claude Code:**
Add MarkdownKB as an MCP server pointing to `http://localhost:9715/mcp` (Streamable HTTP) or run `python mcp_server.py` (stdio).

See [MCP Server](../reference/mcp-server.md) for the full tool reference and setup instructions.

## What's Next

- **[UI Tabs and Plugins](../reference/ui-tabs-and-plugins.md)** — what each tab does, which plugins to enable
- **[CLI](../reference/cli.md)** — search, chat, and manage your KB from the terminal
- **[Scopes and Filtering](scopes-and-filtering.md)** — focus searches on specific folders, tags, or patterns
- **[Configuration](../reference/configuration.md)** — all settings, feature flags, secrets
- **[Embedding Models](embedding-models.md)** — choose and configure embedding models
- **[Architecture](../reference/architecture.md)** — how the system works
- **[Plugins](plugin-development.md)** — enable features and build your own
- **[API Reference](../reference/api.md)** — full endpoint listing
- **[Security](../../SECURITY.md)** — API key setup, network exposure, feature flags
