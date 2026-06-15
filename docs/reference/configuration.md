# Configuration

MarkdownKB is configured through three sources:

- **`config/settings.yaml`** — initial seed configuration. Read exactly once on first startup, then the contents are stored in the settings database. Editing this file after the first run has no effect — use the Settings UI instead.
- **`secrets/`** — Docker secrets for API keys. One key per file, mounted at `/run/secrets/` inside the container. Run `make secrets-init` to scaffold the directory on a fresh clone.
- **`.env`** — environment variables for ports and Docker settings. Copy from `.env.example`.

All three are gitignored. API keys go in `secrets/` files or `.env` — never in `settings.yaml`.

### Settings database

All runtime configuration is stored in `markdownkb_settings.db` in the data directory, alongside the other SQLite databases. On first startup, `config/settings.yaml` is read and its contents are written to this database. After that:

- All Settings UI changes write directly to the database and take effect immediately.
- The database is automatically included in every backup.
- Editing `settings.yaml` has no effect on a running instance — the database is authoritative.

To reset configuration to the YAML file, delete `markdownkb_settings.db` and restart. The YAML will be re-seeded on next boot.

## Precedence

For the small number of settings that can be overridden by environment variables, the resolution order is: **env var / Docker secret → database → built-in default**.

| Setting | Database key | Env var / secret override |
|---------|-------------|--------------------------|
| Server port (local dev) | `server.port` | `API_PORT` |
| Server port (Docker, host-side) | *(n/a — container listens on fixed `9713`)* | `MARKDOWNKB_PORT` |
| MCP port (Docker, host-side) | *(n/a — container listens on fixed `9715`)* | `MARKDOWNKB_MCP_PORT` |
| Ollama URL | `llm.providers[].api_base` | `OLLAMA_API_BASE` |
| LLM API keys | *(not stored)* | `secrets/<provider>_api_key` or `<PROVIDER>_API_KEY` env |
| MarkdownKB API key | *(not stored)* | `secrets/markdownkb_api_key` or `MARKDOWNKB_API_KEY` env |
| Bind address (web/API) | `server.host` | `SERVER_HOST` (Docker) |
| Bind address (MCP) | *(n/a)* | `MARKDOWNKB_MCP_HOST` (Docker) |
| CORS origins | `server.cors_origins` | `CORS_ORIGINS` (comma-separated) |

**When to use which:**
- Use `secrets/` for API keys on shared/production hosts (not visible in `docker inspect`).
- Use `.env` for API keys on single-user/home-lab setups (convenient, but visible in `docker inspect`).
- Use `settings.yaml` to configure a fresh install before first run.
- Use the **Settings UI** (or API) for all changes to a running instance.
- Use `.env` for machine-specific overrides (ports, Docker settings).
- `.mcp.json` (gitignored) — local MCP client config for connecting to other MCP servers. Contains connection tokens, so never commit it.

---

## Sources

| Key | Default | Description |
|-----|---------|-------------|
| `sources` | `[{path: ./docs, writable: false}]` | Directories to scan for markdown files (list of dicts with `path`, optional `writable`, optional `versioned`) |
| `project_roots` | `[]` | Auto-discover docs in cloned repos (see below) |
| `global_ignore` | node_modules, .git, etc. | Glob patterns to skip during indexing |

`global_ignore` patterns are matched against every file path the scanner finds across all source directories. Files matching any pattern are silently skipped — they are never indexed, never appear in the Files tab, and are not included in search or chat context. This is **indexing-only** exclusion: the files still exist on disk and are still versioned by git if your source is versioned.

Use this when you want a subdirectory to be part of a watched source (and therefore versioned) but not indexed. Example:

```yaml
global_ignore:
  - "**/code_reviews/**"   # version these but don't index them
  - "**/node_modules/**"
  - "**/__pycache__/**"
```

Patterns use glob syntax (`**` matches any depth). The API endpoints `POST /api/v1/ignore-patterns` and `DELETE /api/v1/ignore-patterns` add and remove patterns at runtime without a restart — changes take effect on the next scan. Already-indexed files matching a newly-added pattern are **not automatically removed** from the index; use `DELETE /api/v1/files` per-file or trigger a full reindex to clean up.

**`global_ignore` vs. the versioning "Ignore Rules" field:** The Settings UI shows two separate exclusion controls that look similar but are completely independent:

| UI control | Where it appears | What it controls |
|---|---|---|
| **Exclude Patterns** (Sources card) | Bottom of Settings → Sources | `global_ignore` — controls **indexing**. Matching files are skipped by the scanner and never appear in the Files tab or search results. |
| **Ignore Rules** (per versioned source) | Next to each versioned watched directory | Gitignore-syntax patterns written to `.git/info/exclude` inside the managed repo — controls **auto-commit only**. Matching files are not committed to the version history. Has no effect on indexing. |

A file can be indexed but not versioned, versioned but not indexed, both, or neither — the two systems are independent.

Each source is a dict with `path` (string, required), `writable` (boolean, optional — defaults to `true`), and `versioned` (boolean, optional — defaults to the value of `writable`). When `writable: false`, the Write API (`POST/DELETE /api/v1/documents`) and MCP write tools (`save_file`, `delete_file`) return **403 Forbidden** for that source. When `versioned: true` (the default for writable sources), every mdkb-authored write to that source is automatically committed to a per-source managed git repo — see [Versioning](#versioning) below. The bundled `./docs` directory defaults to `writable: false` in the example config to protect project documentation from accidental writes.

```yaml
sources:
  - path: ./docs
    writable: false
  - path: /home/user/docs
    writable: true         # versioned: true is implicit
  - path: /home/user/scratch
    writable: true
    versioned: false       # opt out — e.g. a throwaway scratch dir
```

### Docker Volume Mounts

In Docker, each source directory must be mounted into the container. MarkdownKB auto-generates `config/compose.override.yml` from your sources when you add or remove directories via the Settings UI, and also regenerates it on every startup. The writable flag maps to Docker mount mode: `writable: true` → read-write, `writable: false` → `:ro`.

After adding or removing sources, restart the container to apply the new mount: `make docker-restart`.

Only mounted paths are accessible inside the container — unmounted paths cannot be read or written regardless of what application code or an agent requests. This is an inherent Docker security boundary, not a feature specific to MarkdownKB. See [Docker source mounts](../how-to/docker-deployment.md#source-directory-mounts).

`COMPOSE_FILE` in `.env` tells docker compose to read both files. `config/compose.override.yml` is auto-generated by the app (do not hand-edit). `compose.override.yml` (project root) is user-editable — add extra env vars, custom mounts, or service overrides here; it supports `${VAR}` substitution from `.env`. Both are gitignored — do not commit them.

### Project Roots

Point MarkdownKB at a directory containing cloned repositories and it will automatically discover and index documentation matching your patterns. Each immediate subdirectory is treated as a project — if any files match the `include` patterns (minus `exclude`), that project is watched and indexed. New repos cloned into the root are picked up automatically (~60s).

The `include`/`exclude` patterns apply at **two levels**:

1. **Source discovery** — a subdirectory is only added as a watched source if at least one file matches the include patterns.
2. **File indexing** — when files are scanned or a file event fires, individual files are filtered against the include/exclude patterns. Files not matching any include pattern are silently skipped; files matching any exclude pattern are also skipped.

This means `tests/**` files are never indexed even if the `tests/` directory itself passes the include check for source discovery.

**Pattern semantics:** `*` matches any character except `/`. `**` matches any number of path components. Patterns are matched against the file path relative to the project subdirectory.

| Pattern | What it matches |
|---------|----------------|
| `*.md` | `.md` files at the root of each project |
| `docs/**/*.md` | `.md` files anywhere under `docs/` |
| `**/*.md` | all `.md` files anywhere in the project |

**Via UI:** Settings → Sources → Project Directories → Add. Enter the parent path, an optional display title, and configure include/exclude glob patterns. The title appears in the project listing and the scope picker.

**Via `config/settings.yaml` (before first run):**

```yaml
project_roots:
  - path: /home/user/projects
    include:
      - "*.md"
      - "docs/**/*.md"
    exclude:
      - "CHANGELOG.md"
      - "LICENSE.md"
      - "tests/**"
```

**Docker:** The project root path must be mounted into the container. When you add a project root via the UI, MarkdownKB adds it as a read-only mount in `config/compose.override.yml` automatically. Restart to apply: `make docker-restart`. If a path shows as inaccessible in the Settings UI after restarting, the host path is wrong or the mount failed — verify the path exists on the host.

**Per-source excludes: `project_roots` only.** The `include`/`exclude` patterns above are a feature of `project_roots`, not regular `sources`. A regular `sources` entry has no per-source exclusion — it relies entirely on `global_ignore`. If you need to exclude a subdirectory from one source but not another, either use `global_ignore` with a path-specific pattern (e.g. `**/project_docs/planning_docs/**`) or convert the source to a `project_root` entry.

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

**Token truncation:** All embedding models have a hard token limit (512 for the bundled models). Inputs longer than this limit are silently truncated — the model only sees the first 512 tokens. For prose, 1500 chars is ~375 tokens and fits comfortably. For code-heavy content, tokenization is denser (~2–3 chars/token), so a 1500-char code chunk can exceed 512 tokens and be truncated. This is a property of the model, not the chunker. Switching to a model with a larger context window (e.g. `nomic-embed-text` at 8192 tokens) eliminates this for code-heavy knowledge bases.

Three local ONNX embedding models are available: `all-MiniLM-L6-v2`, `all-MiniLM-L12-v2`, and `bge-small-en-v1.5`. Alternatively, set `provider: remote` to offload embeddings to an Ollama instance or OpenAI-compatible API on another machine. See [embedding-models.md](../how-to/embedding-models.md) for details.

For a detailed explanation of how chunking works — header splitting, paragraph boundaries, breadcrumbs, frontmatter extraction, and how to structure files for best search quality — see [chunking.md](../explanation/chunking.md).

## LLM Providers

| Key | Default | Description |
|-----|---------|-------------|
| `llm.providers` | anthropic, openai, ollama | LLM backends with `name`, `model`, `api_base` |
| `llm.active_provider` | `ollama` | Which provider to use |
| `llm.temperature` | `0.3` | Response randomness (0.0–2.0). Stored per-provider. |
| `llm.max_tokens` | `4096` | Max output tokens. Stored per-provider. |
| `llm.num_ctx` | (unset) | Ollama context window (total input + output). Leave unset for model default. Stored per-provider in `extra_body.num_ctx`. |

Generation parameters (temperature, max_tokens, num_ctx) are stored **per-provider** — each entry in `llm.providers` has its own values. The Settings UI shows the selected provider's parameters and saves to that provider's entry. See [Chat > Configuration](../explanation/chat.md#configuration) for how max_tokens and num_ctx interact.

Model names use the format `provider/model` (e.g. `ollama/qwen3:8b`, `anthropic/claude-sonnet-4-20250514`). For OpenAI-compatible APIs (Venice, Together, etc.) use `openai/<model-name>` with a custom `api_base`.

Providers without an API key are skipped (except Ollama). If the active provider fails, others are tried as fallbacks. API keys are provided via Docker secrets (`secrets/<provider>_api_key`) or environment variables (`<PROVIDER>_API_KEY`).

### Model Catalogs

Static model catalogs live in `app/plugins/catalogs/`. When a provider matches a catalog (by name), the model dropdown in the Settings UI is populated from the catalog. Model info (pricing, context size) is also served from the catalog.

Available catalogs: `venice` (Venice.ai — privacy-preserving OpenAI-compatible API).

### Model Profiles

Model profiles define per-family behavioral configuration — thinking format, default token limits, and context window metadata. They are matched by glob pattern against the model name (provider prefix stripped).

**Built-in profiles** cover common families: DeepSeek R-series, Gemma 4, QwQ, Qwen3, Llama, Mistral, Claude, GPT, Phi, and others. Profile data appears in the Settings UI below the model selector (thinking badge, context size, notes).

**User profiles** in `config/models/*.yaml` take priority over built-ins:

```yaml
# config/models/my-model.yaml
pattern: "my-model*"
thinking_format: xml_tags        # none | reasoning_content | xml_tags
default_max_tokens: 8192
default_temperature: 0.6
context_managed_by: server       # server | api | provider
max_context: 65536
notes: "Optional note shown in the UI."
```

See `config/models/README.md` for the full field reference.

## Retrieval

| Key | Default | Description |
|-----|---------|-------------|
| `retrieval.top_k` | `5` | Chunks to retrieve per query |
| `retrieval.score_threshold` | `0.3` | Minimum similarity score |
| `retrieval.hybrid_search` | `true` | Combine vector + BM25 keyword search |
| `retrieval.bm25_weight` | `0.5` | Keyword vs vector balance |
| `retrieval.intelligent_search.enabled` | `false` | LLM-powered query enhancement (keyword extraction, acronym expansion) |

## Storage

All persistent state (databases, embeddings, models, plugins) lives under a single **data directory**, resolved in order:

1. `MARKDOWNKB_DATA_DIR` environment variable (Docker sets this to `/data`)
2. `storage.data_directory` in `config/settings.yaml` (seed-only; only applied on first run if the settings database is empty)
3. OS-appropriate default via [platformdirs](https://pypi.org/project/platformdirs/):
   - **Linux:** `~/.local/share/markdownkb`
   - **macOS:** `~/Library/Application Support/markdownkb`
   - **Windows:** `%APPDATA%\markdownkb`

| Key | Default | Description |
|-----|---------|-------------|
| `storage.data_directory` | *(auto-detected)* | Root directory for all persistent data |
| `storage.persist_directory` | `{data_directory}/chromadb` | ChromaDB vector store location |
| `storage.collection_name` | `markdownkb` | ChromaDB collection name |

In Docker, compose.yml mounts a named volume to `/data` and the Dockerfile sets `MARKDOWNKB_DATA_DIR=/data`. The app doesn't need to know it's in a container.

## Logging

| Key | Default | Description |
|-----|---------|-------------|
| `logging.level` | `INFO` | Log level: `INFO`, `DEBUG`, or `OFF` (silences all logging). Togglable live from Settings → Logging without restart. |

## Authentication

API key authentication protects all `/api/v1/*` endpoints (except `/api/v1/health` and `/api/v1/setup/generate-key`). When a key is configured, requests must include the `X-MarkdownKB-Key: <key>` header.

### Setup options

**Option 1: Web UI setup (easiest).** When the server is network-exposed (`SERVER_HOST=0.0.0.0`) without a key, a setup banner appears in the UI. Click "Generate API Key" to create one. The key is written to `{data_directory}/secrets/markdownkb_api_key` and takes effect immediately.

**Option 2: Secret file (preferred for shared/production hosts).**

```bash
echo -n "your-key-here" > secrets/markdownkb_api_key
```

Secret files are mounted read-only at `/run/secrets/` and are **not** visible in `docker inspect`.

**Option 3: Environment variable (convenience).**

Add to `.env`:
```
MARKDOWNKB_API_KEY=your-key-here
```

Env vars are visible in `docker inspect` — use secret files instead if others have Docker access on the host.

Keys are resolved in order: `{data_directory}/secrets/` (generated keys) > Docker secret (`/run/secrets/`) > env var (`MARKDOWNKB_API_KEY`). Keys are never stored in the settings database or `settings.yaml`.

When no key is configured and the server binds to localhost only, authentication is disabled (single-user mode).

## Server

| Key | Default | Description |
|-----|---------|-------------|
| `server.host` | `127.0.0.1` | Bind address |
| `server.port` | `9713` | Backend port |
| `server.cors_origins` | `[http://localhost:9714]` | Allowed CORS origins (list). Override with `CORS_ORIGINS` env var (comma-separated). |
| `plans.save_directory` | `{data_directory}/plans` | Where saved plans are written |

### Ports (Docker)

MarkdownKB uses a two-tier port model when running in Docker:

- **Container-internal ports are fixed**: the app always listens on `9713` (web/API) and `9715` (MCP) inside the container. These are implementation details, not user-configurable.
- **Host-facing ports are remappable** via `.env`: `MARKDOWNKB_PORT` and `MARKDOWNKB_MCP_PORT` control which port on *your machine* maps to the fixed container port.

Change the host-facing ports when `9713` or `9715` are already in use on your host:

```dotenv
# .env
MARKDOWNKB_PORT=9720       # host port → container:9713
MARKDOWNKB_MCP_PORT=9722   # host port → container:9715
```

Then `make docker-down && make docker-up`. The app URL becomes `http://localhost:9720` and the MCP URL becomes `http://localhost:9722/mcp`. Inside the container nothing changes — healthchecks, the MCP startup command, and the internal proxy URL all target the fixed container ports.

Local development (outside Docker) uses `API_PORT` and `FRONTEND_PORT` in `.env` — these only affect `make dev` / `run.sh`, not the Docker container.

## Core

Behaviour toggles for built-in features (not plugins).

| Key | Default | Description |
|-----|---------|-------------|
| `core.file_watcher` | `true` | Auto-reindex on file changes |
| `core.deep_research` | `false` | MCTS-powered multi-angle research synthesis |
| `core.agent_skills` | `false` | Agent skill system |
| `core.rate_limiting` | `false` | API rate limiting (slowapi) |
| `core.versioning` | `true` | Git-based file versioning for writable sources |
| `core.update_check` | `true` | Periodic check for new releases |

> **Removed flags (backward-compat only):** `core.rag_chat` and `core.diagnostics` are
> accepted by the migration path so old configs load without error, but they have no active
> gate in production code and are not present in `config/settings.yaml.example`. Setting
> them has no effect.

## MCP

MCP tool flags and transport security. Editable via **Settings → MCP** in the web UI.

| Key | Default | Description |
|-----|---------|-------------|
| `mcp.read_only` | `true` | Disable all write tools (save_document, index_file) regardless of individual flags |
| `mcp.allow_bucket_writes` | `false` | When true, bucket write tools (create/delete/add) are allowed even with `read_only: true`. Buckets are ephemeral and isolated. |

`mcp.read_only` defaults to `true` because MCP clients are AI agents — they act on LLM output, which can be influenced by content in the knowledge base. A document containing adversarial instructions could in theory direct an agent to call write tools on your behalf. Read-only mode eliminates that surface entirely. Enable write tools only when you control what's in the knowledge base and trust the MCP client. See [Write tool security](mcp-server.md#write-tool-security).
| `mcp.save_document` | `false` | Allow MCP clients to write markdown files |
| `mcp.track_history` | `false` | Record MCP search and chat calls to the web UI history sidebar |
| `mcp.allowed_hosts` | `[]` | Allowed `Host` header values for DNS rebinding protection. Use `*` to disable protection entirely, or `hostname:*` for wildcard port matching. Takes effect after MCP server restart. |
| `mcp.allowed_origins` | `[]` | Allowed browser `Origin` header values for cross-origin access. Use `*` to allow all origins, or `http://hostname:*` for wildcard port matching. Takes effect after MCP server restart. |

For LAN access from another machine's browser, add `*` to `allowed_hosts` (disables both host and origin checks) or configure specific entries in both lists. See the [MCP server reference](mcp-server.md#binding-and-dns-rebinding-protection) for pattern details.

## Plugins

Each plugin has `enabled` plus its own config together in one section under `plugins:`. Builtin plugins live in `app/plugins/<name>/`; external plugins are installed to `{data_directory}/plugins/<name>/`.

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
  wiki_compile:
    enabled: false              # Requires LLM — ingest sources into a writable wiki dir, maintain index.md + log.md
  buckets:
    enabled: false
  curate:
    enabled: false              # Corpus growth — harvest bucket-C drafts, two human gates before graduating into the corpus
```

Plugin config (excluding `enabled`) is read/written via the generic API:
- `GET /api/v1/settings/plugins/{name}` — read config
- `PUT /api/v1/settings/plugins/{name}` — update config (shallow merge)

### Migration from legacy format

If your `settings.yaml` seed file still uses the old `features:` section, it is automatically migrated on first startup to the new `core:`/`mcp:`/`plugins:`/`services:` layout and saved to the settings database. No manual intervention needed.

## Services

Shared service configuration used by multiple features. Not plugins — these configure behaviour of core services.

```yaml
services:
  deep_research:
    iterations: 3       # MCTS iterations (1-20)
    n_approaches: 3     # Research angles per iteration
```

## Versioning

Every mdkb-authored write (via the Write API or the `wiki_compile` plugin) is automatically committed to a per-source managed git repo. Users can browse history, view diffs, and restore older revisions from the file viewer (History button).

```yaml
core:
  versioning: true    # global kill-switch; when false, no commits are created

versioning:
  root: ""            # optional override; defaults to {data_dir}/versioning
```

| Key | Default | Description |
|-----|---------|-------------|
| `core.versioning` | `true` | Global kill-switch. Toggle from the Plugins settings tab alongside other core features. When `false`, no commits are created and the `/api/v1/versioning/*` endpoints return 503. |
| `versioning.root` | `{data_dir}/versioning` | Directory that holds the per-source managed git repos. One `<source-hash>/` subdir per versioned source. |

Per-source opt-in/opt-out is controlled by the `versioned` flag on each source (see [Sources](#sources) above). The default is to version writable sources.

The managed repos are mdkb-owned and separate from any user-owned git repo that may already exist at the source path — mdkb writes the gitdir under `versioning.root/<source-hash>/.git` and binds it to the source with `--git-dir` + `--work-tree`, so no `.git` directory appears inside the source itself. Commits are authored as `mdkb <mdkb@localhost>`.

## UI

| Key | Default | Description |
|-----|---------|-------------|
| `ui.file_list_limit` | `5000` | Maximum files returned in file listings |

## MCP Tool Configuration

Each MCP tool has built-in defaults in its source directory (`app/mcp/<tool>/config.yaml`), shipped with the code and never modified at runtime. When you change MCP settings via the Settings UI, your overrides are stored in the settings database under `mcp_configs.<tool>`. The defaults in the source tree are never touched.
