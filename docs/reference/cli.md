# CLI

MarkdownKB includes a command-line interface that wraps the REST API. You can search, chat, manage sources, and work with buckets from the terminal without the web UI or writing curl commands. The CLI talks to a running MarkdownKB instance over HTTP — run it on the same machine as the server, or point it at a remote instance.

```bash
python -m app.cli <command> [options]
```

If you install MarkdownKB as a package, the CLI is also available as `markdownkb`.

## Configuration

The CLI resolves connection settings in this order (first match wins):

1. `--url` flag / `--api-key-file PATH` or `--api-key-stdin`
2. `MARKDOWNKB_URL` / `MARKDOWNKB_API_KEY` environment variables
3. `~/.markdownkb` config file (YAML)
4. Defaults (`http://localhost:9713`, no key)

> **The API key is never accepted as an argv value** (no `--api-key HUNTER2`).
> argv lands in `ps auxww`, shell history, and any wrapper that logs
> command lines. Use a file path (`--api-key-file ~/.config/mdkb/key`),
> stdin (`echo $KEY | markdownkb --api-key-stdin ...`), the env var, or
> the config file instead.

### Config file

Create `~/.markdownkb`:

```yaml
url: http://my-server.local:9713
api_key: your-key-here
```

## Global flags

Every command accepts these:

| Flag | Description |
|------|-------------|
| `--url URL` | Base URL of the MarkdownKB server |
| `--api-key-file PATH` | Read API key from `PATH` |
| `--api-key-stdin` | Read API key from stdin |
| `--json` | Output machine-readable JSON (known-secret fields redacted) instead of pretty text |

On failure, the CLI prints an error to stderr and exits with a non-zero code.

## Commands

### health

Check that the server is reachable and report its status.

```bash
markdownkb health
```

Returns exit code `0` if status is `ok`, `1` otherwise.

### stats

Show index statistics — files, chunks, embedding model, active LLM provider, configured sources.

```bash
markdownkb stats
```

### search

Semantic search against the knowledge base. Uses hybrid retrieval (vector + BM25) configured in the server.

```bash
markdownkb search "authentication flow"
markdownkb search "fastapi routing" --top-k 10
markdownkb search "docker setup" --json | jq '.results[] | .metadata.source_path'
```

| Flag | Description |
|------|-------------|
| `query` | Search query (required, positional) |
| `--top-k N`, `-k N` | Number of results (default: 5) |

### chat

Single-turn RAG chat. The server retrieves relevant chunks and uses the active LLM provider to generate a response.

```bash
markdownkb chat "How does authentication work?"
markdownkb chat "Summarize the deployment process" --json
```

| Flag | Description |
|------|-------------|
| `message` | Question to ask (required, positional) |

Uses the non-streaming `/api/v1/chat` endpoint. For streaming use the web UI or MCP.

### index

Trigger indexing of all configured source directories.

```bash
markdownkb index           # incremental — skips unchanged files
markdownkb index --force   # clear hashes and re-embed everything
```

| Flag | Description |
|------|-------------|
| `--force` | Force full re-index regardless of hashes |

### sources

Manage source directories.

```bash
markdownkb sources                           # list (default action)
markdownkb sources list
markdownkb sources add /home/user/docs
markdownkb sources remove /home/user/docs
markdownkb sources remove /home/user/docs --cleanup
```

| Action | Description |
|--------|-------------|
| `list` | List configured source directories |
| `add <path>` | Add and start watching a directory |
| `remove <path>` | Remove from config |
| `remove <path> --cleanup` | Also unindex all files from that source |

When running in Docker and the added path isn't mounted into the container, the CLI reports `docker_restart_required` with a restart command.

### buckets

Manage temporary document collections. Buckets are isolated from the main knowledge base — each has its own ChromaDB collection.

```bash
markdownkb buckets                                       # list (default)
markdownkb buckets list
markdownkb buckets create research --source /tmp/papers
markdownkb buckets create research --source /tmp/a --source /tmp/b --expires-in 86400
markdownkb buckets search research "key findings"
markdownkb buckets search research "auth patterns" -k 10
markdownkb buckets delete research
```

| Action | Description |
|--------|-------------|
| `list` | List all buckets with file/chunk counts and expiration |
| `create <name>` | Create an empty bucket (add `--source` repeatedly to populate from directories) |
| `search <bucket> <query>` | Search within a bucket (accepts bucket name or ID prefix) |
| `delete <bucket>` | Delete a bucket (accepts name or ID prefix) |

Name resolution: bucket commands that take a `<bucket>` argument accept either the bucket name or a unique ID prefix (4+ chars). Ambiguous matches fail with an error listing the candidates.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (connection failure, HTTP error, invalid input, health degraded) |
| `130` | Interrupted (Ctrl+C) |

## Examples

```bash
# Pipe search results to another tool
markdownkb search "deployment" --json | jq -r '.results[].metadata.source_path' | sort -u

# Use against a remote instance
markdownkb --url http://my-server.local:9713 stats

# Scripted bucket workflow
BUCKET_ID=$(markdownkb buckets create vendor-docs --json | jq -r .id)
markdownkb buckets search vendor-docs "rate limiting"
markdownkb buckets delete vendor-docs

# Quick health check in a cron job
if ! markdownkb health --json > /dev/null; then
    echo "MarkdownKB is down" | mail -s "alert" admin@example.com
fi
```
