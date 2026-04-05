# MDKB -- Value Proposition

## What It Is

MDKB is a self-hosted knowledge base for markdown documents with RAG chat, semantic search, and an MCP server. You point it at directories of markdown files — personal notes, project docs, standards, guides — and it indexes them into a searchable, chat-queryable knowledge base.

Python (FastAPI) backend, React (Vite + TypeScript + Tailwind) frontend, ChromaDB for vectors, SQLite for everything else. Everything runs on one machine. No cloud dependencies.

---

## Who It's For

**Developers and teams who accumulate markdown.** If you have a `docs/` directory, a `knowledge_docs/` folder, architecture decision records, meeting notes, runbooks, or project documentation scattered across repos — MDKB makes all of it searchable and queryable from one place.

**Anyone building with AI agents.** MDKB's MCP server exposes 29+ tools that any MCP-compatible client can call — search, chat, retrieve documents, manage tags, create temporary collections. Claude Code, Claude Desktop, custom agents, or any tool that speaks MCP can use your knowledge base as context.

**People who want to own their data.** No SaaS, no API keys required for core functionality (Ollama runs locally), no data leaving your network. SQLite + ChromaDB on your filesystem. Back it up with `cp`.

---

## The Problem

Knowledge accumulates in markdown files across projects, repos, and directories. Over time you have hundreds of documents but no way to search across them semantically, no way to ask questions grounded in what you've written, and no way to give AI agents access to your institutional knowledge.

The typical workarounds — grep, filesystem search, manually pasting docs into chat windows — don't scale. And they don't compose: you can't easily say "search only these project docs" or "chat with just this subset of my knowledge base."

---

## How It Solves It

1. **Index.** Point MDKB at directories. It scans for markdown, splits files into chunks respecting heading structure, embeds them with a local ONNX model (no external API needed), and stores vectors in ChromaDB.

2. **Search.** Hybrid retrieval combines vector similarity with BM25 keyword matching. Supports quoted exact phrases, tag filtering, folder scoping, and named scopes (saved filter presets). Results link back to source files.

3. **Chat.** RAG-grounded Q&A. Ask a question, MDKB retrieves relevant chunks, builds a context prompt, and streams a response from your configured LLM. Citations link to source documents. Conversation threads are preserved.

4. **Scope.** Tags, scopes, and temp buckets let you control which knowledge is active for a query. Search your entire knowledge base, or just one project's docs, or a temporary collection you created five minutes ago.

5. **Connect.** The MCP server and REST API expose the same capabilities to agents. An AI tool that needs to look something up calls `retrieve` or `chat` over MCP — same pipeline, same results as the web UI.

---

## What Makes It Different

**Plugin-based architecture.** The core is RAG chat — search, graph visualization, planner, tags, export, and buckets are all optional plugins. Enable what you need, disable what you don't. Write your own plugins (a directory with `__init__.py` and a router). External plugins install from GitHub URLs.

**MCP-first agent access.** The standalone MCP server (`mcp_server.py`) exposes 29+ tools over stdio or SSE. Any MCP-compatible client — Claude Code, Claude Desktop, custom agents — can search, chat, retrieve full documents, manage tags, create buckets, and trigger indexing. The MCP server imports core services directly (no HTTP proxy), sharing the same vector store and databases as the web UI. MCP tools accept `scope_id` for project-scoped search, and the `chat` tool supports multi-turn conversations via `thread_id`. SSE transport supports API key auth via `X-MDKB-Key` header or `?token=` query param.

**Scoped search — context curation, not just retrieval.** Three mechanisms for controlling what knowledge is active:

- **Tags and scopes.** Tag documents, create named scopes (folder + tag filter presets), and apply them to search and chat. "Search my infrastructure docs tagged with networking" is a scope.
- **Temp buckets.** Create a temporary collection from arbitrary directories, search it in isolation, delete it when done. Each bucket gets its own ChromaDB collection. Use cases: tutorial transcripts, GitHub `llms.txt` files, conference notes, investigation logs — anything you need searchable temporarily without polluting the permanent knowledge base.
- **Ad-hoc tag filters.** Apply tag filters on the fly in the UI sidebar without creating a named scope.

**Externalized knowledge for any agent system.** MDKB is designed to be one layer in a larger agent stack. Any system that manages agent sessions, orchestration, or workflow can use MDKB as its knowledge backend via MCP or REST. The architecture supports a natural separation of concerns:

| Layer | Examples | What it stores | Lifetime |
|-------|----------|---------------|----------|
| Session memory | Agent orchestrators, CI pipelines, chat tools | Task context, decisions, conversation state | Per-session |
| Permanent knowledge | **MDKB (main index)** | Standards, guides, architecture docs, runbooks | Long-lived |
| Scoped temporary knowledge | **MDKB (temp buckets)** | Project docs, investigation logs, tutorial notes | Hours to days |

An agent working on a task reads its session context from whatever orchestrator manages it, searches MDKB for organizational standards, and searches a temp bucket for project-specific docs. Each query returns focused results. The model asks specific questions and gets specific answers — no large context window needed. A local model running on Ollama with an 8K context window can participate effectively because the knowledge is externalized, not stuffed into a prompt.

This composability is intentional. MDKB doesn't try to be the orchestrator, the task runner, or the session manager. It handles knowledge — permanent and temporary — and exposes it through standard interfaces (MCP tools, REST API) that any upstream system can call.

**Self-hosted, local-first.** Runs on a single machine. ChromaDB and SQLite on your filesystem. Embedding models run locally via ONNX (CPU, no GPU required). LLM providers are configurable — Ollama (local), Anthropic, OpenAI, Venice, or any OpenAI-compatible API. No cloud dependencies for core functionality.

**Human UI + agent API.** The same features are accessible from both the browser and from agents. The React frontend has tabs for chat, search, planner, graph, file browsing, and settings. The MCP server and REST API expose equivalent capabilities. The bucket selector appears in the chat and search sidebars — a human picks a bucket from a dropdown, an agent passes `bucket_id` in a tool call. Same pipeline, same results.

---

## What's Built

### Core
| Feature | Status |
|---|---|
| RAG chat with citation links and source maps | Built |
| Hybrid search (vector + BM25 keyword matching) | Built |
| Markdown indexing with heading-aware chunking | Built |
| File watcher (auto-reindex on changes) | Built |
| Thread management (create, rename, delete, history) | Built |
| Multiple LLM providers with fallback chain | Built |
| Local ONNX embeddings (3 models, no external API) | Built |
| API key authentication (X-MDKB-Key header) | Built |
| Docker deployment | Built |

### Plugins
| Plugin | Description | Status |
|---|---|---|
| Search | Search history, versions, compare, AI summaries, deep research (MCTS) | Built |
| Tags | Tag storage, CRUD, folder auto-tagging, AI tag generation | Built |
| Graph | Knowledge graph visualization (3D force-directed, clustering) | Built |
| Planner | MCTS-powered implementation plan generation | Built |
| Buckets | Temporary scoped collections with independent vector storage | Built |
| Export | Conversation export (markdown, JSON) | Built |
| Write API | Document creation via HTTP | Built |

### MCP Server
| Feature | Status |
|---|---|
| 29+ tools (search, chat, documents, tags, buckets, graph, planner) | Built |
| stdio + SSE transports | Built |
| Read-only mode, per-tool gating, plugin-aware tool registration | Built |
| History tracking (MCP searches/chats appear in web UI sidebar) | Built |

### Infrastructure
| Feature | Status |
|---|---|
| Docker multi-stage build (app + MCP server as separate services) | Built |
| Rate limiting (slowapi) | Built |
| Typed request schemas (Pydantic) | Built |
| Test suite (pytest, 128+ tests) | Built |
| Model catalogs (Venice, Ollama) | Built |

---

## Deployment

Self-hosted. Docker or bare metal.

```
docker compose up --build -d    # Docker (recommended)
.venv/bin/python -m app.main    # bare metal
```

ChromaDB + SQLite for storage — no separate database to manage. Single port (default 9713). Built-in React UI served from the same process. MCP server runs as a second container/process on port 9715.

---

## The Core Bet

Most knowledge management tools optimize for ingestion — get everything in, worry about retrieval later. MDKB makes the opposite bet: that retrieval quality and context control matter more than scale. Hybrid search, scoped filtering, temp buckets, and citation tracking all serve the same goal — when you ask a question, the answer should come from the right documents, not just the nearest vectors.

There's a second bet: that the same knowledge base should serve both humans and agents equally. Every feature in the web UI has an equivalent MCP tool or API endpoint. The knowledge base is not a human tool that agents can kind of use, or an agent tool with a dashboard bolted on — it's both, by design.
