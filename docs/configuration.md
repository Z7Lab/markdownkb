# Configuration

mdkb is configured through three sources:

- **`config/settings.yaml`** — primary configuration (sources, LLM providers, retrieval tuning, feature flags, storage). Copy from `config/settings.yaml.example`.
- **`secrets/`** — Docker secrets for API keys. One key per file, mounted at `/run/secrets/` inside the container. See `secrets/README.md`.
- **`.env`** — environment variables for ports and Docker settings. Copy from `.env.example`.

All three are gitignored. API keys should **only** be stored in `secrets/` (or env vars as a fallback) — never in `settings.yaml`.

## Precedence

Docker secrets take highest priority, then environment variables, then `settings.yaml`:

| Setting | settings.yaml | secrets / .env |
|---------|--------------|----------------|
| Server port | `server.port` | `API_PORT` |
| Ollama URL | `llm.providers[].api_base` | `OLLAMA_API_BASE` |
| LLM API keys | *(not supported)* | `secrets/<provider>_api_key` or `<PROVIDER>_API_KEY` env |
| MDKB API key | *(not supported)* | `secrets/mdkb_api_key` or `MDKB_API_KEY` env |
| Bind address | `server.host` | `MDKB_HOST` (Docker) |
| CORS origins | `server.cors_origins` | `CORS_ORIGINS` (comma-separated) |

**When to use which:**
- Use `secrets/` for all API keys (Docker mounts them read-only at `/run/secrets/`).
- Use `settings.yaml` for non-secret configuration — it's the canonical config file.
- Use `.env` for machine-specific overrides (ports, Docker settings).

Settings changed via the **Settings** tab in the UI are saved back to `settings.yaml`.

---

## Sources

| Key | Default | Description |
|-----|---------|-------------|
| `sources` | `[./docs]` | Directories to scan for markdown files |
| `project_roots` | `[]` | Auto-discover docs in cloned repos (see below) |
| `global_ignore` | node_modules, .git, etc. | Glob patterns to skip |

### Project Roots

Point mdkb at a directory containing cloned repositories and it will automatically discover and index documentation matching your patterns:

```yaml
project_roots:
  - path: /home/user/projects
    include:
      - "*.md"
      - "docs/**/*.md"
    exclude:
      - "CHANGELOG.md"
      - "LICENSE.md"
```

Each immediate subdirectory of `path` is treated as a project. If any files match the `include` patterns (minus `exclude`), that project directory is watched and indexed. New repos cloned into the root are picked up automatically (~60s).

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
| `llm.providers` | anthropic, openai, ollama | LLM backends with `name`, `model`, `api_base` |
| `llm.active_provider` | `ollama` | Which provider to use |
| `llm.temperature` | `0.3` | Response randomness (0.0–2.0) |
| `llm.max_tokens` | `2048` | Max output tokens |
| `llm.num_ctx` | (unset) | Ollama context window override. Leave unset for the model's built-in default. Set higher (e.g. `32768`) to use more context for longer documents. Only applies to Ollama providers. |

Model names use [LiteLLM format](https://docs.litellm.ai/docs/providers): `provider/model` (e.g. `ollama/qwen3:8b`, `anthropic/claude-3-5-sonnet-20241022`). For OpenAI-compatible APIs (Venice, Together, etc.) use `openai/<model-name>` with a custom `api_base`.

Providers without an API key are skipped (except Ollama). If the active provider fails, others are tried as fallbacks. API keys are provided via Docker secrets (`secrets/<provider>_api_key`) or environment variables (`<PROVIDER>_API_KEY`).

### Model Catalogs

Static model catalogs live in `app/plugins/catalogs/`. When a provider matches a catalog (by name), the model dropdown in the Settings UI is populated from the catalog instead of querying the LiteLLM registry. Model info (pricing, context size) is also served from the catalog.

Available catalogs: `venice` (Venice.ai — privacy-preserving OpenAI-compatible API).

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

## Authentication

API key authentication protects all `/api/*` endpoints (except `/api/health`). When a key is configured, requests must include the `X-MDKB-Key: <key>` header.

Set the key via Docker secret or environment variable:

```bash
# Docker secret (preferred)
echo -n "your-key-here" > secrets/mdkb_api_key

# Or environment variable
export MDKB_API_KEY=your-key-here
```

When no key is configured, authentication is disabled.

## Server

| Key | Default | Description |
|-----|---------|-------------|
| `server.host` | `127.0.0.1` | Bind address |
| `server.port` | `9713` | Backend port |
| `server.cors_origins` | `[http://localhost:9714]` | Allowed CORS origins (list). Override with `CORS_ORIGINS` env var (comma-separated). |
| `plans.save_directory` | `./data/plans` | Where saved plans are written |

## Features

Feature flags toggle optional modules. All security-sensitive features default to off.

| Key | Default | Description |
|-----|---------|-------------|
| `features.rag_chat` | `true` | Chat with RAG |
| `features.file_watcher` | `true` | Auto-reindex on file changes |
| `features.search` | `true` | Search tab with history, summaries, and query enhancement |
| `features.export` | `true` | Conversation export (markdown/JSON) |
| `features.mcp_filesystem` | `false` | MCP file browsing tool |
| `features.mcp_terminal` | `false` | MCP terminal tool |
| `features.mcp_tag_generator` | `false` | AI tag generation for markdown files |
| `features.mcts_planner` | `true` | MCTS plan generation |
| `features.deep_research` | `false` | MCTS-powered multi-angle research synthesis for search summaries |
| `features.agent_skills` | `false` | Agent skill system |
| `features.write_api` | `false` | HTTP endpoint for creating/updating markdown files |
| `features.diagnostics` | `false` | Diagnostic endpoints |
| `features.knowledge_graph` | `true` | 3D document similarity graph visualization |
| `features.rate_limiting` | `false` | API rate limiting (slowapi) |

## Plugin Configuration

Plugins can have their own configuration under the `plugins:` section. Each plugin defines its own defaults internally — you only need to add entries here to override them.

```yaml
plugins:
  search:
    chunk_multiplier: 10        # chunks fetched per result (higher = more diversity)
    exact_phrase_multiplier: 20  # chunk multiplier when quoted phrases are used
    exact_phrase_matching: true   # enable Google-style "quoted phrase" exact matching
  deep_research:
    iterations: 3               # MCTS research iterations (1-20, higher = deeper but slower)
    n_approaches: 3             # number of research angles per iteration
```

Plugin config is read/written via the generic API:
- `GET /api/settings/plugins/{name}` — read config
- `PUT /api/settings/plugins/{name}` — update config (shallow merge)

## UI

| Key | Default | Description |
|-----|---------|-------------|
| `ui.file_list_limit` | `5000` | Maximum files returned in file listings |

## MCP Tool Configuration

Each MCP tool has a default config in its source directory (`app/mcp/<tool>/config.yaml`). When you modify MCP settings via the Settings UI, overrides are saved to `config/mcp/<tool>.yaml` (created automatically on first save). The defaults in the source tree are never modified.
