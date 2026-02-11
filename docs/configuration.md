# Configuration

mdkb is configured through two files:

- **`config/settings.yaml`** — primary configuration (sources, LLM providers, retrieval tuning, feature flags, storage). Copy from `config/settings.yaml.example`.
- **`.env`** — environment variables for ports, Docker settings, and API keys. Copy from `.env.example`.

Both are gitignored. The example files are tracked.

## Precedence

Environment variables override `settings.yaml` for the settings they overlap on:

| Setting | settings.yaml | .env / Environment |
|---------|--------------|-------------------|
| Server port | `server.port` | `API_PORT` |
| Ollama URL | `llm.providers[].api_base` | `OLLAMA_API_BASE` |
| API keys | `llm.providers[].api_key` | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` |
| Bind address | `server.host` | `MDKB_HOST` (Docker) |

**When to use which:**
- Use `settings.yaml` for everything — it's the canonical config file with all options.
- Use `.env` for machine-specific overrides (ports, Docker, API keys you don't want in YAML).

Settings changed via the **Settings** tab in the UI are saved back to `settings.yaml`.

---

## Sources

| Key | Default | Description |
|-----|---------|-------------|
| `sources` | `[./docs]` | Directories to scan for markdown files |
| `global_ignore` | node_modules, .git, etc. | Glob patterns to skip |

## Embeddings

| Key | Default | Description |
|-----|---------|-------------|
| `embeddings.model` | `all-MiniLM-L6-v2` | Embedding model (ONNX, no PyTorch) |
| `embeddings.chunk_size` | `512` | Max characters per chunk |
| `embeddings.chunk_overlap` | `50` | Overlap between chunks |

Three embedding models are available: `all-MiniLM-L6-v2`, `all-MiniLM-L12-v2`, and `bge-small-en-v1.5`. Install and switch between them from the **Settings** tab. See [embedding-models.md](embedding-models.md) for details.

## LLM Providers

| Key | Default | Description |
|-----|---------|-------------|
| `llm.providers` | anthropic, openai, ollama | LLM backends with `name`, `model`, `api_key`, `api_base` |
| `llm.active_provider` | `ollama` | Which provider to use |
| `llm.temperature` | `0.3` | Response randomness |
| `llm.max_tokens` | `2048` | Max response length |

Model names use [LiteLLM format](https://docs.litellm.ai/docs/providers): `provider/model` (e.g. `ollama/qwen3:8b`, `anthropic/claude-3-5-sonnet-20241022`).

Providers without an `api_key` are skipped (except Ollama). If the active provider fails, others are tried as fallbacks.

## Retrieval

| Key | Default | Description |
|-----|---------|-------------|
| `retrieval.top_k` | `5` | Chunks to retrieve per query |
| `retrieval.score_threshold` | `0.3` | Minimum similarity score |
| `retrieval.hybrid_search` | `true` | Combine vector + BM25 keyword search |
| `retrieval.bm25_weight` | `0.5` | Keyword vs vector balance |
| `retrieval.intelligent_search.enabled` | `false` | LLM-powered query enhancement (keyword extraction, acronym expansion) |

## Storage

| Key | Default | Description |
|-----|---------|-------------|
| `storage.persist_directory` | `./data/chromadb` | ChromaDB vector store location |
| `storage.collection_name` | `mdkb` | ChromaDB collection name |

## Logging

| Key | Default | Description |
|-----|---------|-------------|
| `logging.level` | `INFO` | Log level for UI log viewer (`INFO` or `DEBUG`) |

## Server

| Key | Default | Description |
|-----|---------|-------------|
| `server.host` | `127.0.0.1` | Bind address |
| `server.port` | `9713` | Backend port |
| `plans.save_directory` | `./data/plans` | Where saved plans are written |

## Features

Feature flags toggle optional modules. All security-sensitive features default to off.

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

## MCP Tool Configuration

Each MCP tool has a default config in its source directory (`app/mcp/<tool>/config.yaml`). When you modify MCP settings via the Settings UI, overrides are saved to `config/mcp/<tool>.yaml` (created automatically on first save). The defaults in the source tree are never modified.
