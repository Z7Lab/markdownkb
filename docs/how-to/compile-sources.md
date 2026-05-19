# Compile Sources into a Wiki

This walkthrough uses the `wiki_compile` plugin to turn a folder of raw source material into a set of LLM-synthesized summary pages that MarkdownKB indexes automatically. At the end you'll have a compiled wiki that search, chat, and the doc map can all use.

For background on why this exists and the three-tier model it respects, read [wiki-compile.md](../explanation/wiki-compile.md) first.

## Prerequisites

- MarkdownKB running (Docker or native).
- A configured LLM provider (Ollama, Venice, Anthropic, etc.). The plugin uses the same provider the chat and search summarize features use.
- One source you want to ingest. Papers, transcripts, long blog posts, vendor docs — anything dense and unstructured works well. Short, already-well-structured docs don't benefit from compilation.

## 1. Enable the plugin

In `config/settings.yaml`:

```yaml
plugins:
  wiki_compile:
    enabled: true
```

Restart the container: `make docker-down && make docker-up`. Plugin enablement is read at startup.

## 2. Create a wiki

A *wiki* is a named, persistent target the plugin manages for you. The plugin creates the directory, registers it as a writable source, and (in Docker) updates `config/compose.override.yml` automatically.

```bash
curl -X POST http://localhost:9713/api/v1/wiki-compile/wikis \
  -H "Content-Type: application/json" \
  -d '{ "name": "research" }'
```

Response:

```json
{
  "id": "cf27d84510aa",
  "name": "research",
  "path": "/data/wikis/research",
  "created_at": "2026-04-14 15:09:43",
  "last_ingest_at": null,
  "page_count": 0,
  "docker_restart_required": false
}
```

By default the wiki lands at `{data_directory}/wikis/{name}/` — inside the existing data-dir mount, so `docker_restart_required` is `false` and you can ingest immediately.

If you'd rather keep the wiki in a git-versioned location elsewhere, pass an explicit `path`:

```bash
curl -X POST http://localhost:9713/api/v1/wiki-compile/wikis \
  -H "Content-Type: application/json" \
  -d '{ "name": "research", "path": "/home/user/wikis/research" }'
```

The response will then flag `docker_restart_required: true` — run `make docker-down && make docker-up` before ingesting so the new bind mount activates.

## 3. Ingest a source

Reference the wiki by name:

```bash
curl -X POST http://localhost:9713/api/v1/wiki-compile/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "source_path": "/home/user/downloads/some-paper.md",
    "wiki": "research",
    "force": false
  }'
```

Response:

```json
{
  "status": "ok",
  "source_path": "/home/user/downloads/some-paper.md",
  "target_source": "/data/wikis/research",
  "wiki": "research",
  "pages_written": [
    "summaries/some-paper.md",
    "log.md",
    "index.md"
  ],
  "existing_pages_used": [],
  "summary_preview": "# Some Paper — Key Claim\n\n...",
  "summary_chars": 1620
}
```

The LLM call typically takes 5–30 seconds depending on the provider and model. First ingest also creates `index.md` and `log.md`; subsequent ingests update them.

`existing_pages_used` lists related pages from this wiki that were passed to the LLM as context. On the very first ingest it's empty; on later ingests it surfaces the cross-references the new summary will reference.

## 4. Verify the output

```bash
ls /data/wikis/research/
# index.md  log.md  summaries/

cat /data/wikis/research/summaries/some-paper.md
```

The summary page has a `# Title` heading, 2–4 paragraphs naming specific entities and claims, and a `## Source` section citing the raw source path. The format is deliberate — see [the explanation doc](../explanation/wiki-compile.md) for the reasoning.

## 5. Use the compiled wiki

Because the wiki's path is a configured writable source, MarkdownKB's indexer picks up the compiled pages automatically on the next watch cycle. After a few seconds:

- **Search** surfaces the summary pages alongside raw documents. Use a scope that includes the wiki's path if you want to limit queries to compiled material.
- **Chat** retrieves from the compiled pages when relevant. Questions that previously required the LLM to re-synthesize the source material every time now pull from the pre-synthesized summary.
- **Doc Map** plots the compiled pages with the rest of the graph. Pages on related topics cluster together.
- **MCP clients** (Claude Code, Claude Desktop, custom agents) see the compiled pages through the same tools as everything else.

## Ingest from the UI

When `wiki_compile` is enabled, every Markdown file viewer in mdkb gets a **Compile** button next to the file actions. Clicking it opens a dialog that:

- Lists your existing wikis. Pick one and click Compile.
- If you have no wikis yet, lets you create one inline (just type a name) and uses it for the ingest.
- Shows the result — pages written, summary preview, and which existing pages were cross-referenced.

Same flow as the curl examples above, just driven from the UI.

## Multiple wikis

Karpathy's pattern is one wiki per topic or domain — research, work, personal, hobby, a specific book, a specific project. Create as many as you want, each gets its own directory:

```bash
curl -X POST http://localhost:9713/api/v1/wiki-compile/wikis -d '{"name":"research"}'
curl -X POST http://localhost:9713/api/v1/wiki-compile/wikis -d '{"name":"work"}'
curl -X POST http://localhost:9713/api/v1/wiki-compile/wikis -d '{"name":"personal"}'
```

Each ingest call picks one. Cross-referencing only fires within a single wiki — the retriever is scoped to the wiki's directory, so a "research" ingest won't pull in "work" pages as context.

## List, deregister, delete

```bash
# List
curl http://localhost:9713/api/v1/wiki-compile/wikis

# Deregister (directory + files preserved on disk)
curl -X DELETE http://localhost:9713/api/v1/wiki-compile/wikis/research
```

Deregistering removes the wiki from MarkdownKB's tracking (drops the WikiDB row and the writable-source entry) but leaves the directory intact. To truly delete, remove the directory yourself with your filesystem tools.

## Idempotency and re-ingestion

Ingesting the same source twice without `force=true` returns a 400 error pointing at the existing summary. To overwrite:

```bash
curl -X POST http://localhost:9713/api/v1/wiki-compile/ingest \
  -d '{"source_path":"/home/user/downloads/some-paper.md","wiki":"research","force":true}'
```

The log appends a new entry so the history of overwrites is preserved.

## Batch-ingesting a directory

There's no batch verb, but a shell loop works fine:

```bash
for src in /home/user/downloads/papers/*.md; do
  curl -s -X POST http://localhost:9713/api/v1/wiki-compile/ingest \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg src "$src" --arg w research \
           '{source_path: $src, wiki: $w, force: false}')"
  echo
done
```

Run serially rather than in parallel — concurrent LLM calls will queue anyway, and serial output keeps the log readable.

## When things go wrong

- **404 "Wiki not found"** — the wiki name doesn't exist. Call `GET /wikis` to see what's available, or create one with `POST /wikis`.
- **404 "source_path not found"** — the source file isn't readable from inside the container. In Docker, make sure the parent directory is mounted. Check `docker inspect markdownkb --format '{{range .Mounts}}{{.Source}}{{"\n"}}{{end}}'`.
- **503 "LLM request failed"** — no usable LLM provider. Check `Settings > LLM` in the web UI or the `llm.providers` block in `settings.yaml`.
- **400 "summary page already exists"** — the source was already ingested. Pass `force=true` to overwrite, or delete the existing summary manually if you want a clean slate.
- **`docker_restart_required: true` in a create response** — you used a custom path outside the project/data dir. Run `make docker-down && make docker-up` before ingesting so the new bind mount activates.
