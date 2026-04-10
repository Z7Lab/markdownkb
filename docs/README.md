# Documentation

Organized using [Diataxis](https://diataxis.fr/) — how-to guides for tasks, reference for lookups, explanation for understanding.

## How-To Guides

Task-oriented. Follow these when you're trying to get something done.

| Document | Description |
|----------|-------------|
| [Getting Started](how-to/getting-started.md) | Install, configure, index your first docs, search and chat |
| [Local LLM Setup](how-to/local-llm-setup.md) | Step-by-step Ollama install and model setup (macOS, Linux, Windows) |
| [API Key Setup](how-to/api-key-setup.md) | When you need a key, how to set one, how to use it |
| [Embedding Models](how-to/embedding-models.md) | Choose and configure local ONNX or remote embedding (Ollama, cloud) |
| [Remote LLM Setup](how-to/remote-llm-setup.md) | Connect Docker MarkdownKB to remote Ollama or llama.cpp servers |
| [Scopes and Filtering](how-to/scopes-and-filtering.md) | Named filter presets — folders, tags, exclude patterns, persistent sidebar state |
| [AI Tagging](how-to/ai-tagging.md) | LLM-powered tag generation — preview, apply, bulk, manual tagging |
| [Plugin Development](how-to/plugin-development.md) | Build custom plugins — structure, manifest, databases, MCP tools |

## Third-Party Integration

Self-contained setup guides for external services. Each covers install, config, and verification in one doc.

| Document | Description |
|----------|-------------|
| [Ollama Remote Setup](thirdparty/ollama-remote-setup.md) | Run Ollama on a separate machine with network and security config |
| [llama.cpp Setup](thirdparty/llamacpp-setup.md) | Build and run llama-server from source for CPU-optimized inference |
| [llama.cpp API](thirdparty/llamacpp-api.md) | llama.cpp OpenAI-compatible API guide and MarkdownKB integration |

## Reference

Look things up mid-task. Structured for scanning, not reading top-to-bottom.

| Document | Description |
|----------|-------------|
| [UI Tabs and Plugins](reference/ui-tabs-and-plugins.md) | What each tab does, which plugins enable which tabs, plugin dependencies |
| [Architecture](reference/architecture.md) | System overview, components, data flow, storage layer, plugin system |
| [Configuration](reference/configuration.md) | All settings keys, feature flags, `.env` vs `settings.yaml` precedence |
| [API](reference/api.md) | Full REST endpoint listing for all features |
| [MCP Server](reference/mcp-server.md) | 32 MCP tools, transports (stdio/Streamable HTTP), authentication, scope support |
| [CLI](reference/cli.md) | Command-line interface — search, chat, index, sources, buckets, over HTTP |
| [LLM Benchmarking](reference/llm-benchmarking.md) | Measuring tokens/second for Ollama and llama.cpp |

## Explanation

Background and reasoning. Read when you want to understand why, not how.

| Document | Description |
|----------|-------------|
| [Chat](explanation/chat.md) | Chat tab — RAG conversations, threads, continue, save, scoped chat, sources |
| [Search & AI Summaries](explanation/search.md) | Search tab features — results, AI summaries, deep research, history, versioning |
| [Retrieval & Hybrid Search](explanation/retrieval.md) | How search works — vector similarity, BM25 keywords, score fusion, tuning |
| [Chunking & Indexing](explanation/chunking.md) | How files are split into chunks, heading structure, search quality |
| [Doc Map](explanation/docmap.md) | 3D document similarity visualization — sliders, clustering, word clouds, interaction |
| [Knowledge Graph](explanation/knowledge-graph.md) | Entity extraction, typed relationships, document similarity |
| [Buckets](explanation/buckets.md) | Temporary isolated document collections — built-in docs, comparison workflows |
| [Planner](explanation/planner.md) | MCTS-based implementation planner with skill reviews |
| [Philosophy](explanation/philosophy.md) | The markdown-first paradigm — why tokens are value |
| [Value Proposition](explanation/value-proposition.md) | What MarkdownKB is, who it's for, what makes it different |
| [Security](../SECURITY.md) | Threat model, API key auth, feature flags, network exposure |
