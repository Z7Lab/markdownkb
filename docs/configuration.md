# Configuration

mdkb is configured through three sources:

- **`config/settings.yaml`** — primary configuration (sources, LLM providers, retrieval tuning, feature flags, storage). Copy from `config/settings.yaml.example`.
- **`secrets/`** — Docker secrets for API keys. One key per file, mounted at `/run/secrets/` inside the container. See `secrets/README.md`.
- **`.env`** — environment variables for ports and Docker settings. Copy from `.env.example`.

All three are gitignored. API keys go in `secrets/` files or `.env` — never in `settings.yaml`.

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
- Use `secrets/` for API keys on shared/production hosts (not visible in `docker inspect`).
- Use `.env` for API keys on single-user/home-lab setups (convenient, but visible in `docker inspect`).
- Use `settings.yaml` for non-secret configuration — it's the canonical config file.
- Use `.env` for machine-specific overrides (ports, Docker settings).
- `.mcp.json` (gitignored) — local MCP client config for connecting to other MCP servers. Contains connection tokens, so never commit it.

Settings changed via the **Settings** tab in the UI are saved back to `settings.yaml`.

### Reloading configuration

If you edit `settings.yaml` on the host (e.g. via another tool or agent), the running container does not pick up changes automatically. Call the reload endpoint to re-read from disk without restarting:

```bash
curl -X POST http://localhost:9713/api/settings/reload
```

API-driven changes (via the Settings UI) take effect immediately — they update the live config and save to disk in one step. The reload endpoint is only needed for host-side file edits.

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

| Key | Code default | Recommended | Description |
|-----|-------------|-------------|-------------|
| `embeddings.provider` | `local` | `local` | `local` (ONNX on CPU) or `remote` (Ollama/OpenAI-compatible API) |
| `embeddings.model` | `all-MiniLM-L6-v2` | `bge-small-en-v1.5` | Local ONNX embedding model |
| `embeddings.api_base` | — | — | Remote embedding API URL (when provider is `remote`) |
| `embeddings.remote_model` | `nomic-embed-text` | — | Model name on the remote server |
| `embeddings.api_type` | `ollama` | — | `ollama` or `openai` (OpenAI-compatible) |
| `embeddings.api_key` | — | — | API key for authenticated providers. Prefer `secrets/embedding_api_key` or `EMBEDDING_API_KEY` env var. |
| `embeddings.chunk_size` | `512` | `1500` | Max characters per chunk |
| `embeddings.chunk_overlap` | `50` | `150` | Overlap between consecutive chunks |

The code defaults (512/50) are conservative fallbacks. The recommended values (1500/150) are set in `settings.yaml.example` and optimized for `bge-small-en-v1.5` (1500 chars &asymp; 375 tokens, within the model's 512-token window). After changing chunk settings, re-index all files for the new values to take effect.

Three local ONNX embedding models are available: `all-MiniLM-L6-v2`, `all-MiniLM-L12-v2`, and `bge-small-en-v1.5`. Alternatively, set `provider: remote` to offload embeddings to an Ollama instance or OpenAI-compatible API on another machine. See [embedding-models.md](embedding-models.md) for details.

For a detailed explanation of how chunking works — header splitting, paragraph boundaries, breadcrumbs, frontmatter extraction, and how to structure files for best search quality — see [chunking.md](chunking.md).

## LLM Providers

| Key | Default | Description |
|-----|---------|-------------|
| `llm.providers` | anthropic, openai, ollama | LLM backends with `name`, `model`, `api_base` |
| `llm.active_provider` | `ollama` | Which provider to use |
| `llm.temperature` | `0.3` | Response randomness (0.0–2.0) |
| `llm.max_tokens` | `2048` | Max output tokens |
| `llm.num_ctx` | (unset) | Ollama context window override. Leave unset for the model's built-in default. Set higher (e.g. `32768`) to use more context for longer documents. Only applies to Ollama providers. |

Model names use the format `provider/model` (e.g. `ollama/qwen3:8b`, `anthropic/claude-sonnet-4-20250514`). For OpenAI-compatible APIs (Venice, Together, etc.) use `openai/<model-name>` with a custom `api_base`.

Providers without an API key are skipped (except Ollama). If the active provider fails, others are tried as fallbacks. API keys are provided via Docker secrets (`secrets/<provider>_api_key`) or environment variables (`<PROVIDER>_API_KEY`).

### Model Catalogs

Static model catalogs live in `app/plugins/catalogs/`. When a provider matches a catalog (by name), the model dropdown in the Settings UI is populated from the catalog. Model info (pricing, context size) is also served from the catalog.

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

API key authentication protects all `/api/*` endpoints (except `/api/health` and `/api/setup/generate-key`). When a key is configured, requests must include the `X-MDKB-Key: <key>` header.

### Setup options

**Option 1: Web UI setup (easiest).** When the server is network-exposed (`MDKB_HOST=0.0.0.0`) without a key, a setup banner appears in the UI. Click "Generate API Key" to create one. The key is written to `data/secrets/mdkb_api_key` and takes effect immediately.

**Option 2: Secret file (preferred for shared/production hosts).**

```bash
echo -n "your-key-here" > secrets/mdkb_api_key
```

Secret files are mounted read-only at `/run/secrets/` and are **not** visible in `docker inspect`.

**Option 3: Environment variable (convenience).**

Add to `.env`:
```
MDKB_API_KEY=your-key-here
```

Env vars are visible in `docker inspect` — use secret files instead if others have Docker access on the host.

Keys are resolved in order: `data/secrets/` (generated keys) > Docker secret (`secrets/`) > env var (`MDKB_API_KEY`). Keys are never stored in `settings.yaml`.

When no key is configured and the server binds to localhost only, authentication is disabled (single-user mode).

## Server

| Key | Default | Description |
|-----|---------|-------------|
| `server.host` | `127.0.0.1` | Bind address |
| `server.port` | `9713` | Backend port |
| `server.cors_origins` | `[http://localhost:9714]` | Allowed CORS origins (list). Override with `CORS_ORIGINS` env var (comma-separated). |
| `plans.save_directory` | `./data/plans` | Where saved plans are written |

## Core

Behaviour toggles for built-in features (not plugins).

| Key | Default | Description |
|-----|---------|-------------|
| `core.rag_chat` | `true` | Chat with RAG |
| `core.file_watcher` | `true` | Auto-reindex on file changes |
| `core.deep_research` | `false` | MCTS-powered multi-angle research synthesis |
| `core.agent_skills` | `false` | Agent skill system |
| `core.diagnostics` | `false` | Diagnostic endpoints |
| `core.rate_limiting` | `false` | API rate limiting (slowapi) |

## MCP

MCP tool enable flags.

| Key | Default | Description |
|-----|---------|-------------|
| `mcp.read_only` | `true` | Disable all write tools (save_document, index_file) regardless of individual flags |
| `mcp.allow_bucket_writes` | `false` | When true, bucket write tools (create/delete/add) are allowed even with `read_only: true`. Buckets are ephemeral and isolated. |
| `mcp.filesystem` | `false` | MCP file browsing tool |
| `mcp.terminal` | `false` | MCP terminal tool |
| `mcp.save_document` | `false` | Allow MCP clients to write markdown files |

## Plugins

Each plugin has `enabled` plus its own config together in one section under `plugins:`. Builtin plugins live in `app/plugins/<name>/`; external plugins are installed to `data/plugins/<name>/`.

```yaml
plugins:
  search:
    enabled: true
    chunk_multiplier: 10
    exact_phrase_multiplier: 20
    exact_phrase_matching: true
  export:
    enabled: true
  tags:
    enabled: true
    ai_generation: false        # AI-powered tag generation (LLM-based)
  docmap:
    enabled: true
  knowledge_graph:
    enabled: false              # Requires LLM — extracts entities and relationships from docs
  planner:
    enabled: false
  write_api:
    enabled: false
  buckets:
    enabled: false
```

Plugin config (excluding `enabled`) is read/written via the generic API:
- `GET /api/settings/plugins/{name}` — read config
- `PUT /api/settings/plugins/{name}` — update config (shallow merge)

### Migration from legacy format

If your `settings.yaml` still uses the old `features:` section, it is automatically migrated on startup to the new `core:`/`mcp:`/`plugins:`/`services:` layout. The migrated file is saved back to disk. No manual intervention needed.

## Services

Shared service configuration used by multiple features. Not plugins — these configure behaviour of core services.

```yaml
services:
  deep_research:
    iterations: 3       # MCTS iterations (1-20)
    n_approaches: 3     # Research angles per iteration
```

## UI

| Key | Default | Description |
|-----|---------|-------------|
| `ui.file_list_limit` | `5000` | Maximum files returned in file listings |

## MCP Tool Configuration

Each library module has a default config in its source directory (`app/lib/<module>/config.yaml`). When you modify MCP settings via the Settings UI, overrides are saved to `config/mcp/<tool>.yaml` (created automatically on first save). The defaults in the source tree are never modified.
