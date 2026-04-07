# Chunking & Indexing Pipeline

How mdkb splits markdown files into searchable chunks. Understanding this pipeline helps you structure documents for better search quality.

## Overview

Indexing is a **two-pass** process:

1. **Header splitting** — divide the file into logical sections by markdown headings (H1–H6)
2. **Size-limited chunking** — split each section into chunks that fit the embedding model's token window

Each chunk is enriched with a **breadcrumb** (file path + heading context) and **frontmatter metadata** before being embedded and stored in the vector database.

```
Markdown file
  → frontmatter extraction (title, tags)
  → header-based section splitting (H1–H6)
  → size-limited paragraph chunking (1500 chars default)
    → sentence-boundary fallback for oversized paragraphs
    → min_chunk_size merge for short fragments
  → breadcrumb prepending per chunk
  → embedding (ONNX model, CPU)
  → storage (ChromaDB + TrackingDB)
```

## Pass 1: Header Splitting

The parser (`app/ingestion/parser.py`) splits markdown content at **any** heading level — `#` through `######`. Each heading creates a section boundary.

```python
# Regex: matches H1 through H6
r"^(#{1,6})\s+(.+)$"
```

- Content **before the first heading** becomes its own section (with an empty heading)
- Each heading starts a new section containing everything until the next heading
- If a file has **no headings at all**, the entire content becomes a single section — it still gets chunked by size in Pass 2

## Pass 2: Size-Limited Chunking

Each section from Pass 1 is further split to fit within the configured `chunk_size`. The algorithm respects natural text boundaries:

1. **Paragraph boundaries** (`\n\n`) — preferred split point
2. **Sentence boundaries** (`. `, `! `, `? `) — fallback when a single paragraph exceeds `chunk_size`
3. **Overlap** — the last `chunk_overlap` characters of each chunk are prepended to the next chunk for context continuity

### Short chunk merging

Chunks shorter than 200 characters (e.g., a bare heading with no body text) are **not emitted standalone**. Instead, they're kept as a prefix for the next chunk. This prevents heading-only micro-chunks that would waste embedding capacity.

## Configuration

Chunking is configured in `config/settings.yaml` under the `embeddings` section:

```yaml
embeddings:
  model: bge-small-en-v1.5
  chunk_size: 1500       # max characters per chunk
  chunk_overlap: 150     # overlap between consecutive chunks
```

| Setting | Location | Runtime value | Code default | Description |
|---------|----------|---------------|--------------|-------------|
| `chunk_size` | `embeddings.chunk_size` | **1500** | 512 | Maximum characters per chunk |
| `chunk_overlap` | `embeddings.chunk_overlap` | **150** | 50 | Characters of overlap between chunks |
| `min_chunk_size` | hardcoded in `parser.py` | **200** | 200 | Minimum chars to emit a chunk standalone |

### Config hierarchy

Settings are loaded from `config/settings.yaml` at startup. If a key is missing from YAML, the code default applies. There are **no environment variable overrides** for chunk settings — edit the YAML and restart.

The code defaults (512/50) exist in two places:
- `app/config/__init__.py` — Settings property fallback
- `app/ingestion/parser.py` — function signature default (never used in production; callers always pass settings values)

### Relationship to embedding model

The chunk size should fit within the embedding model's token window:

| Model | Max tokens | Recommended chunk_size |
|-------|-----------|----------------------|
| all-MiniLM-L6-v2 | 256 tokens | 512–800 chars |
| all-MiniLM-L12-v2 | 256 tokens | 512–800 chars |
| bge-small-en-v1.5 | 512 tokens | 1000–1500 chars |

At ~4 characters per token, 1500 chars &asymp; 375 tokens, which fits comfortably within bge-small-en-v1.5's 512-token limit. With overlap, a stored chunk can reach ~1650 characters (~412 tokens) — still within bounds.

### Changing chunk size

After changing `chunk_size` or `chunk_overlap`, you must **re-index all files** for the new settings to take effect on existing content. New and modified files will use the new settings automatically via the file watcher.

To re-index everything: delete the ChromaDB data directory (`data/chromadb/`) and restart, or use the CLI: `python -m app.cli index --force`.

## Breadcrumb Prepending

Before embedding, each chunk gets a **breadcrumb** prepended that identifies the source file and section:

```
From: deliberative-ai/sandbox-knowledge-transfer-2026-03-16T1148/orchestration-summary > Key Decisions

# Key Decisions

We decided to persist session IDs so agents can resume...
```

The breadcrumb is part of the text that gets embedded, so the **file path and heading are baked into the embedding vector**. This means:

- The directory name (e.g., `sandbox-knowledge-transfer`) improves retrieval for topic-related queries
- Descriptive headings (e.g., "Session Resume Strategy") improve retrieval for section-specific queries
- Even without perfect keyword matches, the breadcrumb provides semantic context

## YAML Frontmatter

mdkb parses YAML frontmatter using the `python-frontmatter` library. Two fields are **actively extracted** into chunk metadata:

| Field | Used for |
|-------|---------|
| `title` | Stored per-chunk, surfaces in search results |
| `tags` | Stored per-chunk, enables tag-based filtering and scope queries |

Other frontmatter keys (e.g., `date`, `type`, `orchestration_id`) are **preserved** in the chunk's `frontmatter` metadata dict but are not currently used for search filtering or ranking.

Example frontmatter:

```yaml
---
title: "Orchestration Summary — Sandbox Knowledge Transfer"
tags:
  - deliberation
  - sandbox-knowledge-transfer
  - summary
orchestration_id: abc123
date: 2026-03-16
---
```

If frontmatter YAML is malformed, the parser logs a warning and continues — the file is still indexed, but `title` and `tags` metadata will be empty.

## Practical Guidance

### Headings improve search quality

Headings serve two purposes in chunking:

1. **Logical section boundaries** — content under one heading stays together (up to `chunk_size`)
2. **Breadcrumb context** — the heading text is embedded into every chunk from that section

Use **descriptive headings** that contain the key concepts someone would search for:

```markdown
## Decision: Session Resume Uses --resume Flag     <-- good
## Item 6                                          <-- bad
```

### No artificial breaks needed

You do **not** need to insert artificial headings to control chunk boundaries. The size-based second pass handles large sections automatically — a 30KB section under one heading gets split into ~20 chunks at paragraph/sentence boundaries.

Headings improve *search precision* (better breadcrumbs) but are not required for correct chunking.

### Write for search

- **Use natural language** — "We decided to persist session IDs" matches more queries than terse bullet points
- **Be consistent with terminology** — use the same phrase ("session resume") everywhere, not variants ("re-attach to sandbox", "reconnect")
- **Front-load key terms in headings** — they become part of every chunk's breadcrumb

### File size

There is no file size limit for indexing. Large files (50K+ characters) are handled efficiently:
- Chunked into ~35 pieces (at 1500 chars each)
- Processed in batches of 500 chunks
- Hash-based change detection skips unchanged files on re-index

Separate files per topic are still recommended for **search result granularity** — mdkb groups search results by file, so separate files mean separate search results with distinct relevance scores.

## Implementation Files

| File | Purpose |
|------|---------|
| `app/ingestion/parser.py` | Header splitting, paragraph chunking, breadcrumbs, frontmatter |
| `app/ingestion/indexer.py` | Orchestrates parse → embed → store pipeline |
| `app/ingestion/watcher.py` | File change detection, triggers re-indexing |
| `app/ingestion/scanner.py` | File discovery across source directories |
| `app/config/__init__.py` | Settings properties (`chunk_size`, `chunk_overlap`) |
| `config/settings.yaml` | Runtime configuration |
