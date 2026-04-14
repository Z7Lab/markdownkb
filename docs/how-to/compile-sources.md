# Compile Sources into a Wiki

This walkthrough uses the `wiki_compile` plugin to turn a folder of raw source material into a set of LLM-synthesized summary pages that MarkdownKB indexes automatically. At the end you'll have a compiled wiki in a writable source directory, with an index, a chronological log, and summary pages that search, chat, and the doc map can all use.

For background on why this exists and the three-tier model it respects, read [wiki-compile.md](../explanation/wiki-compile.md) first.

## Prerequisites

- MarkdownKB running (Docker or native).
- A configured LLM provider (Ollama, Venice, Anthropic, etc.). The plugin uses the same provider the chat and search summarize features use.
- One source you want to ingest. For this walkthrough we'll use a file already on disk; see [Ingesting from a bucket](#ingesting-from-a-bucket) below if your material lives in a temp bucket.

## 1. Enable the plugin

In `config/settings.yaml`:

```yaml
plugins:
  wiki_compile:
    enabled: true
```

Restart the container: `make docker-down && make docker-up`. Plugin enablement is read at startup.

## 2. Configure a writable target source

The compiled wiki has to land in a source configured with `writable: true`. It must be a *different* directory from your canonical docs — the plugin will refuse to write anywhere that isn't explicitly writable, and by convention you don't compile into your human-authored sources.

Pick a directory and add it:

```yaml
sources:
  - path: /home/user/wiki          # your compiled wiki target
    writable: true
```

Restart: `make docker-down && make docker-up` (required for new source mounts in Docker).

Verify the target is recognized:

```bash
curl http://localhost:9713/api/wiki-compile/targets
```

The list that comes back is the set of directories the plugin will accept as an ingest target.

## 3. Ingest a source

Pick a source file on disk. Papers, transcripts, long blog posts, vendor docs — anything dense and unstructured works well. Short, already-well-structured docs don't benefit from compilation.

```bash
curl -X POST http://localhost:9713/api/wiki-compile/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "source_path": "/home/user/downloads/some-paper.md",
    "target_source": "/home/user/wiki",
    "force": false
  }'
```

Response:

```json
{
  "status": "ok",
  "source_path": "/home/user/downloads/some-paper.md",
  "target_source": "/home/user/wiki",
  "pages_written": [
    "summaries/some-paper.md",
    "log.md",
    "index.md"
  ],
  "summary_preview": "# Some Paper — Key Claim\n\nThe paper argues...",
  "summary_chars": 1620
}
```

The LLM call typically takes 5–30 seconds depending on the provider and model. First ingest also creates `index.md` and `log.md`; subsequent ingests update them.

## 4. Verify the output

```bash
ls /home/user/wiki/
# index.md  log.md  summaries/

cat /home/user/wiki/summaries/some-paper.md
# # Some Paper — Key Claim
# 
# The paper argues that ...
# (2-4 paragraphs synthesizing the source)
#
# ## Source
#
# /home/user/downloads/some-paper.md
```

The summary page has a `# Title` heading, 2–4 paragraphs naming specific entities and claims, and a `## Source` section citing the raw source path. The format is deliberate — see [the explanation doc](../explanation/wiki-compile.md) for the reasoning.

## 5. Use the compiled wiki

Because `/home/user/wiki/` is a configured source, MarkdownKB's indexer picks up the compiled pages automatically on the next watch cycle. After a few seconds:

- **Search** surfaces the summary pages alongside raw documents. Use a scope that includes `/home/user/wiki/` if you want to limit queries to compiled material.
- **Chat** retrieves from the compiled pages when relevant. Questions that previously required the LLM to re-synthesize the source material every time now pull from the pre-synthesized summary.
- **Doc Map** plots the compiled pages with the rest of the graph. Pages on related topics cluster together.
- **MCP clients** (Claude Code, Claude Desktop, custom agents) see the compiled pages through the same tools as everything else.

## Idempotency and re-ingestion

Ingesting the same source twice without `force=true` returns a 400 error pointing at the existing summary. To overwrite:

```bash
curl -X POST http://localhost:9713/api/wiki-compile/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "source_path": "/home/user/downloads/some-paper.md",
    "target_source": "/home/user/wiki",
    "force": true
  }'
```

The log appends a new entry so the history of overwrites is preserved.

## Ingesting from a bucket

If your raw material lives in a temp bucket, the source path still needs to be a file on disk. Bucket docs typically come from files the user already has; use the file path, not the bucket id:

```bash
# The raw file on disk
curl -X POST http://localhost:9713/api/wiki-compile/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "source_path": "/home/user/downloads/buckets/my-bucket/doc.md",
    "target_source": "/home/user/wiki"
  }'
```

(A future version may accept `bucket_id + bucket_doc_path` directly. For now, use the filesystem path.)

## Batch-ingesting a directory

v1 doesn't have a batch verb, but a shell loop works fine:

```bash
for src in /home/user/downloads/papers/*.md; do
  curl -s -X POST http://localhost:9713/api/wiki-compile/ingest \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg src "$src" --arg tgt /home/user/wiki \
           '{source_path: $src, target_source: $tgt, force: false}')"
  echo
done
```

Run serially rather than in parallel — concurrent LLM calls will queue anyway, and serial output keeps the log readable.

## When things go wrong

- **400 "target_source is not a configured writable source"** — the path you passed isn't in `/api/wiki-compile/targets`. Either add it to `sources:` with `writable: true` and restart, or pick a path that's already there.
- **404 "source_path not found"** — the source file isn't readable from inside the container. In Docker, make sure the parent directory is mounted. Check `docker inspect markdownkb --format '{{range .Mounts}}{{.Source}}{{"\n"}}{{end}}'`.
- **503 "LLM request failed"** — no usable LLM provider. Check `Settings > LLM` in the web UI or the `llm.providers` block in `settings.yaml`.
- **400 "summary page already exists"** — the source was already ingested. Pass `force=true` to overwrite, or delete the existing summary manually if you want a clean slate.
