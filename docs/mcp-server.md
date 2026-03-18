# MCP Server

mdkb includes a standalone MCP (Model Context Protocol) server that exposes core knowledge base capabilities to any MCP-compatible client — Claude Desktop, the personal-dispatcher, or custom agents.

The server runs as a **separate process** alongside the FastAPI app. It imports core services directly (no HTTP proxy), sharing the same `config/settings.yaml`, vector store, and SQLite databases.

## Quick Start

```bash
# SSE transport via Makefile (recommended for local dev)
make mcp

# stdio transport (for Claude Desktop, pipes, etc.)
.venv/bin/python mcp_server.py

# SSE transport (manual)
.venv/bin/python mcp_server.py --sse --port 9715
```

## Tools

| Tool | Description |
|------|-------------|
| `search` | Hybrid vector + keyword search across indexed documents |
| `search_documents` | Search and return full document content (deduplicated by file) |
| `chat` | RAG-grounded Q&A using the configured LLM |
| `get_document` | Read the full content of an indexed markdown file |
| `list_documents` | List all indexed documents (optionally filter by status) |
| `plan` | Generate an implementation plan using MCTS (saved to plan database) |
| `save_document` | Save a markdown file to a watched source directory |
| `index_file` | Re-index a single markdown file |
| `list_sources` | List configured source directories |
| `stats` | Knowledge base statistics (document counts, index status, vector count) |

### search

```
search(query: "authentication flow", top_k: 5)
→ {results: [{content, source, score}, ...], total}
```

### search_documents

```
search_documents(query: "authentication flow", top_k: 3, max_chars: 15000)
→ {documents: [{path, title, content, score}, ...], total_chars}
```

Unlike `search` which returns individual chunks, this returns the **full content** of the top matching files (deduplicated by source path). Ideal for embedding complete documents into prompts. The `max_chars` budget prevents oversized responses — documents are included in score order until the budget is exhausted, with truncation if needed.

### plan

```
plan(request: "Design a caching layer for the API", iterations: 3, n_approaches: 3, save: true)
→ {plan: "...", approaches: [{content, score}, ...], plan_id: "abc123"}
```

Uses MCTS to explore multiple approaches grounded in your knowledge base, then synthesizes the best plan. Plans are saved to the plan database by default (visible in the Planner tab sidebar with a bot icon). Set `save: false` to skip persistence.

### chat

```
chat(message: "How does the auth middleware work?")
→ {response: "The auth middleware checks..."}
```

Uses the same RAG pipeline as the web UI chat — retrieves relevant chunks, builds a context prompt, and calls the active LLM provider.

### get_document

```
get_document(path: "/home/user/docs/auth.md")
→ {path, content, status, chunk_count}
```

Only reads files within configured source directories. Returns an error for paths outside sources or unindexed files.

### list_documents

```
list_documents(status: "complete")
→ {documents: [{path, status, chunk_count}, ...], total}
```

Status filter is optional. Valid values: `complete`, `pending`, `error`.

### save_document

```
save_document(
  path: "captures/2026-03-15-meeting.md",
  content: "# Meeting Notes\n\n...",
  source: "",       # defaults to first configured source
  overwrite: false
)
→ {status: "created", path, relative_path, source}
```

Path must be relative, must end in `.md`, and cannot contain `..` traversal. The file is written to disk and automatically picked up by the file watcher for indexing.

**Disabled by default.** Enable in `config/settings.yaml`:

```yaml
mcp:
  save_document: true
```

### index_file

```
index_file(path: "/home/user/docs/new-file.md")
→ {status, chunk_count, path}
```

Re-indexes the file (parse → embed → store). File must be within a configured source directory and end in `.md`.

### list_sources

```
list_sources()
→ {sources: ["/home/user/docs", "/home/user/notes"]}
```

### stats

```
stats()
→ {total_files, complete, pending, error, total_chunks, vector_count}
```

## Transports

| Transport | Flag | Use case |
|-----------|------|----------|
| **stdio** | (default) | Claude Desktop, subprocess pipes, local agents |
| **SSE** | `--sse` | Network clients, remote agents |

### stdio (default)

The server reads JSON-RPC messages from stdin and writes responses to stdout. Logs go to stderr. This is the standard transport for Claude Desktop and similar tools.

### SSE

```bash
.venv/bin/python mcp_server.py --sse --host 0.0.0.0 --port 9715
```

| Flag | Default | Description |
|------|---------|-------------|
| `--sse` | off | Enable SSE transport |
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `9715` | Listen port |

## Claude Desktop Configuration

Add to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mdkb": {
      "command": "/path/to/mdkb/.venv/bin/python",
      "args": ["/path/to/mdkb/mcp_server.py"],
      "cwd": "/path/to/mdkb"
    }
  }
}
```

## Docker

The MCP server runs as a separate service in `compose.yml`:

```bash
make up          # starts both mdkb and mdkb-mcp
make logs        # tails logs for both services
```

The `mdkb-mcp` service uses SSE transport on port 9715 (configurable via `MDKB_MCP_PORT`). It shares the same data volume and config as the main app.

Connect from another service on the Docker network:

```
http://mdkb-mcp:9715/sse
```

Or from the host:

```
http://localhost:9715/sse
```

## Architecture

The MCP server shares the same storage as the FastAPI app:

- **Config**: Reads `config/settings.yaml` via the same `Settings` singleton
- **Vector store**: ChromaDB at `data/chromadb/`
- **Tracking DB**: SQLite at `data/mdkb.db`
- **Embeddings**: Same ONNX models, same embedding pipeline

On startup, the server loads embedding models (`load_models()`), initializes its own instances of `VectorStore`, `TrackingDB`, and `Retriever`, then auto-discovers and registers MCP tools. If the vector store is empty, it runs an initial index automatically.

DNS rebinding protection is disabled so that containers (e.g. sandbox agents) can reach the MCP server via `host.docker.internal`.

### Tool Auto-Discovery

Tools are auto-discovered from `app/mcp/tools/`. Each tool module exports:

- `TOOL` dict — with `name` (str), optional `feature_flag` (str or None), and optional `write` (bool)
- `handler` callable — the MCP tool function

Feature-gated tools (where `feature_flag` is set) are only registered when enabled in `config/settings.yaml` under `mcp:`. Tools marked `write: True` are also disabled when `mcp.read_only` is enabled — this provides a single switch to make the MCP server read-only regardless of individual tool flags.

To add a new MCP tool, create a new `.py` file in `app/mcp/tools/` following the existing pattern.

> **Note**: The MCP server and FastAPI app can run simultaneously — SQLite uses WAL mode for safe concurrent reads. However, only one process should write to the vector store at a time to avoid conflicts.
