# Documentation

## Getting Started

| Document | Description |
|----------|-------------|
| [Getting Started](getting-started.md) | Install, configure, index your first docs, search and chat |
| [Local LLM Setup](local-llm-setup.md) | Step-by-step Ollama install and model setup (macOS, Linux, Windows) |
| [API Key Setup](api-key-setup.md) | When you need a key, how to set one, how to use it |

## How-To Guides

| Document | Description |
|----------|-------------|
| [Embedding Models](embedding-models.md) | Choose between local ONNX and remote embedding (Ollama, OpenAI, Venice) |
| [Ollama Remote Setup](ollama-remote-setup.md) | Run Ollama on a separate machine with SSH tunneling |
| [llama.cpp Setup](llamacpp-setup.md) | Build and run llama-server from source for CPU-optimized inference |
| [Remote LLM Setup](mdkb-remote-llm-setup.md) | Connect Docker mdkb to remote Ollama or llama.cpp servers |
| [Plugin Development](plugin-development.md) | Build custom plugins — structure, manifest, config, lifecycle hooks |
| [Chunking & Indexing](chunking.md) | How files are split into chunks; heading structure and search quality tips |

## Reference

| Document | Description |
|----------|-------------|
| [Configuration](configuration.md) | All settings keys, feature flags, `.env` vs `settings.yaml` precedence |
| [API Reference](api.md) | Full REST endpoint listing for all features |
| [MCP Server](mcp-server.md) | 32 MCP tools, transports (stdio/SSE), authentication, scope support |
| [MCP Tools](mcp-tools.md) | Optional embedded tools — filesystem, terminal, AI tag generation |
| [CLI](cli.md) | Command-line interface (index, search, add-source, stats) |
| [llama.cpp API](llamacpp-api.md) | llama.cpp OpenAI-compatible API guide and mdkb integration |
| [LLM Benchmarking](llm-benchmarking.md) | Measuring tokens/second for Ollama and llama.cpp |

## Understanding

| Document | Description |
|----------|-------------|
| [Architecture](architecture.md) | System overview, components, data flow, storage layer, plugin system |
| [Knowledge Graph](knowledge-graph.md) | Entity extraction, typed relationships, and document similarity visualization |
| [Planner](planner.md) | MCTS-based implementation planner with skill reviews |
| [Security](../SECURITY.md) | Threat model, API key auth, feature flags, network exposure |

## Project

| Document | Description |
|----------|-------------|
| [Philosophy](../PHILOSOPHY.md) | The markdown-first paradigm — why tokens are value, compounding knowledge |
| [Value Proposition](../VALUE_PROP.md) | What mdkb is, who it's for, what makes it different |
