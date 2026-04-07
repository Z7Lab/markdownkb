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
| [Remote LLM Setup](how-to/remote-llm-setup.md) | Connect Docker mdkb to remote Ollama or llama.cpp servers |
| [Plugin Development](how-to/plugin-development.md) | Build custom plugins — structure, manifest, databases, MCP tools |

## Third-Party Integration

Self-contained setup guides for external services. Each covers install, config, and verification in one doc.

| Document | Description |
|----------|-------------|
| [Ollama Remote Setup](thirdparty/ollama-remote-setup.md) | Run Ollama on a separate machine with network and security config |
| [llama.cpp Setup](thirdparty/llamacpp-setup.md) | Build and run llama-server from source for CPU-optimized inference |
| [llama.cpp API](thirdparty/llamacpp-api.md) | llama.cpp OpenAI-compatible API guide and mdkb integration |

## Reference

Look things up mid-task. Structured for scanning, not reading top-to-bottom.

| Document | Description |
|----------|-------------|
| [Architecture](reference/architecture.md) | System overview, components, data flow, storage layer, plugin system |
| [Configuration](reference/configuration.md) | All settings keys, feature flags, `.env` vs `settings.yaml` precedence |
| [API](reference/api.md) | Full REST endpoint listing for all features |
| [MCP Server](reference/mcp-server.md) | 32 MCP tools, transports (stdio/SSE), authentication, scope support |
| [MCP Tools](reference/mcp-tools.md) | Optional embedded tools — filesystem, terminal, AI tag generation |
| [CLI](reference/cli.md) | Command-line interface (index, search, add-source, stats) |
| [LLM Benchmarking](reference/llm-benchmarking.md) | Measuring tokens/second for Ollama and llama.cpp |

## Explanation

Background and reasoning. Read when you want to understand why, not how.

| Document | Description |
|----------|-------------|
| [Chunking & Indexing](explanation/chunking.md) | How files are split into chunks, heading structure, search quality |
| [Knowledge Graph](explanation/knowledge-graph.md) | Entity extraction, typed relationships, document similarity |
| [Planner](explanation/planner.md) | MCTS-based implementation planner with skill reviews |
| [Philosophy](explanation/philosophy.md) | The markdown-first paradigm — why tokens are value |
| [Value Proposition](explanation/value-proposition.md) | What mdkb is, who it's for, what makes it different |
| [Security](../SECURITY.md) | Threat model, API key auth, feature flags, network exposure |
