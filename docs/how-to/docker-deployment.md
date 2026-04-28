# Docker Deployment

This guide covers running MarkdownKB in Docker — from a minimal first-run to a hardened LAN deployment with persistent data, secrets, and image variants.

MarkdownKB ships as a docker compose stack — clone the repo, copy the example config, and `make docker-up`. There's no separate `docker run` workflow; the compose stack is the supported deployment.

## First-run

```bash
git clone <repo-url> markdownkb
cd markdownkb
cp .env.example .env
cp config/settings.yaml.example config/settings.yaml
make secrets-init          # create secrets/ dir and empty placeholder files
make docker-build && make docker-up
```

Open `http://localhost:9713`. The compose stack runs the main app (port 9713) and the MCP sidecar (port 9715), with persistent data in `~/.local/share/markdownkb` and Docker secrets for API keys.

After every code or dependency change, use `make docker-rebuild` (`--no-cache`) — `make docker-build` reuses cached layers and can occasionally miss frontend changes.

## API keys: secrets vs env vars

You have two ways to hand keys to the container. Use one or the other; resolution order is **secret file > env var > empty**.

### Secret files (preferred)

The `secrets/` directory at the repo root holds plain-text key files, one per provider. Compose mounts them into the container at `/run/secrets/<name>` — they never appear in `docker inspect` and never enter env-var process listings.

On a fresh clone, run `make secrets-init` first to create the directory and empty placeholder files. Then write your keys:

```bash
make secrets-init
echo -n "sk-ant-PLACEHOLDER" > secrets/anthropic_api_key
echo -n "sk-..."     > secrets/openai_api_key
echo -n "..."        > secrets/venice_api_key
```

The MarkdownKB API key (used by the web UI and MCP server for auth) lives in the same place:

```bash
openssl rand -hex 16 > secrets/markdownkb_api_key
# or click "Generate API Key" in the setup banner — it writes to this file too
```

Run `make docker-restart` after writing or changing a secret. Add a new provider by creating `<provider>_api_key` and listing it under `secrets:` in `compose.yml`.

### Env vars

Set them in `.env` (gitignored, copied from `.env.example`):

```
ANTHROPIC_API_KEY=sk-ant-PLACEHOLDER
OPENAI_API_KEY=sk-...
```

Convenient, but the keys are visible to anyone who can run `docker inspect <container>`. Use this only on a single-user machine.

## Network exposure

By default the container binds to `127.0.0.1` — only this machine can reach it. To expose to your LAN:

```
# in .env
SERVER_HOST=0.0.0.0                # web UI on every interface
MARKDOWNKB_MCP_HOST=0.0.0.0       # MCP server on every interface
```

For a tighter setup, bind to a specific IP instead of `0.0.0.0`:

```
SERVER_HOST=<your-server-ip>
MARKDOWNKB_MCP_HOST=<your-server-ip>
```

That listens on only that one interface — a VPN or Docker bridge on the same host stays unexposed.

When you go beyond localhost, set a `markdownkb_api_key` secret too. The setup banner will warn you if you've enabled network access without one. See [API Key Setup](api-key-setup.md) for the full reasoning.

## Persistent data

The compose stack mounts `${MARKDOWNKB_DATA_DIR:-~/.local/share/markdownkb}` to `/data` inside the container. This holds:

- All SQLite databases (chats, searches, plans, presets, scopes, tracking, knowledge graph, plugin DBs)
- The ChromaDB vector store
- Plans, plugin data, downloaded embedding models

To use a different location, set `MARKDOWNKB_DATA_DIR` in `.env` before first run. To migrate to a new location later, take a backup via **Settings → Backup & Restore**, change the path, restart, restore.

## Source directory mounts

MarkdownKB indexes files inside its container, so any directory listed under `sources:` in `config/settings.yaml` must also be mounted. The UI does this automatically — when you add a source via **Settings → Sources**, it writes a mount entry to `config/compose.override.yml` and prompts you to restart.

If you edit `settings.yaml` directly, mount the directory yourself in `compose.yml`:

```yaml
volumes:
  - /home/user/notes:/home/user/notes:ro      # read-only
  - /home/user/captures:/home/user/captures   # writable
```

**Security boundary:** Only mounted paths exist inside the container. Any path that isn't explicitly mounted is simply inaccessible — the container process cannot read or write to it, regardless of what an application or agent attempts. This means the blast radius of any write operation (including MCP write tools like `save_file`) is strictly bounded to the directories you've chosen to mount. See [MCP write tool security](../reference/mcp-server.md#write-tool-security).

**Two override files, one purpose:** MarkdownKB uses two override files for source mounts:

- `compose.override.yml` (project root) — written by the app when running on the host (dev mode)
- `config/compose.override.yml` — written by the app when running inside Docker (bind-mounted via `./config:/app/config`)

Both are listed in `.env` as `COMPOSE_FILE=compose.yml:compose.override.yml:config/compose.override.yml`, so `docker compose up -d` (no `-f` flags) loads them both automatically.

**Warning — explicit `-f` flags override `COMPOSE_FILE`:** When using variant builds (`-f compose.full.yml`, etc.), Docker ignores the `COMPOSE_FILE` env var entirely. Both override files must be listed explicitly, or source mounts will be missing and the scanner will prune all indexed files on startup. All `make docker-build-*` targets handle this correctly — if you run `docker compose` by hand, always include both: `-f compose.override.yml -f config/compose.override.yml`.

## Image variants

MarkdownKB publishes two image tags:

| Tag | Contents |
| --- | -------- |
| `latest` | Base image — all core features, no optional extras |
| `full` | Base + optional extras: YouTube transcript extraction, PDF/DOCX/XLSX/PPTX conversion |

Use `full` if you want the converter plugin to pull full transcripts from YouTube URLs or convert PDF, Word, Excel, and PowerPoint files to markdown.

### Pulling a specific tag

Set the image in your compose.yml or override:

```yaml
services:
  markdownkb:
    image: markdownkb/markdownkb:full   # or :latest
    # remove `build: .` when using a pre-built image
  markdownkb-mcp:
    image: markdownkb/markdownkb:full
    # remove `build: .`
```

### Building the full image locally

```bash
make docker-build-full
```

This passes the extras build arg through `compose.full.yml`. Use `make docker-rebuild-full` for a clean no-cache build.

### Building a custom image from your settings

`compose.full.yml` is an all-or-nothing preset. If you only want some converter sub-converters (e.g. YouTube and DOCX but not PDF), generate a `compose.custom.yml` tailored to your `config/settings.yaml`:

```bash
make generate-compose    # reads config/settings.yaml, writes compose.custom.yml
make docker-build-custom # builds and starts with only your enabled extras
```

`compose.custom.yml` is gitignored — regenerate it any time you change converter sub-converter settings.

### Note on YouTube ToS

`youtube_transcript_api` fetches transcripts via YouTube's public timedtext API. Including it in your image is fine (MIT license), but your use of it is subject to [YouTube's Terms of Service](https://www.youtube.com/t/terms). Use it for personal knowledge bases — not for bulk scraping.

## Extending the base image

The base image is intentionally minimal — text-only indexing, no OCR, no PDF rasterisers. If you need extra tools (tesseract for OCR, poppler-utils for high-quality PDF extraction, a custom plugin from GitHub, etc.), copy [`Dockerfile.example`](../../Dockerfile.example) to `Dockerfile.custom`, edit the lines that apply, then build:

```bash
docker build -f Dockerfile.custom -t my-markdownkb .
```

Point your compose.yml at the custom image:

```yaml
services:
  markdownkb:
    image: my-markdownkb
    # remove `build: .`
```

Or build it via compose by setting `build.dockerfile: Dockerfile.custom`.

## Backups before upgrades

Always take a backup before pulling a newer image:

1. **Settings → Backup & Restore → Download Backup**
2. `make docker-down`
3. `docker pull markdownkb/markdownkb:latest` (or the version tag you want)
4. `make docker-up`

If anything misbehaves, restore the backup via the same panel and you're back where you were. See [Backup and Restore](backup-and-restore.md).

## Common operations

| Task                              | Command                          |
| --------------------------------- | -------------------------------- |
| Start                             | `make docker-up`                 |
| Stop                              | `make docker-down`               |
| Restart (config-only changes)     | `make docker-restart`            |
| Tail logs                         | `make docker-logs`               |
| Open a shell in the container     | `make docker-shell`              |
| Rebuild (after code changes)      | `make docker-rebuild`            |
| Build full variant                | `make docker-build-full`         |
| Status                            | `make docker-ps`                 |

## See also

- [Getting Started](getting-started.md) — first-run walk-through
- [API Key Setup](api-key-setup.md) — when and how to set the MarkdownKB auth key
- [MCP Server](../reference/mcp-server.md) — Streamable HTTP transport, allowed hosts, rate limits
- [Backup and Restore](backup-and-restore.md) — export and re-import full state
