# API Key Setup

MarkdownKB can require an API key on all `/api/v1/*` endpoints. This guide explains when you need one, what it protects, and how to set it up.

## When Do You Need an API Key?

**Local-only use (default):** No key needed. MarkdownKB binds to localhost by default — only your machine can access it.

**Network-exposed use:** Set a key. If you've exposed MarkdownKB to other machines — `MARKDOWNKB_HOST=0.0.0.0` in `.env` for Docker, or `SERVER_HOST=0.0.0.0` for a bare-metal/`make dev` run — anyone on your network can read, write, and delete from your knowledge base without a key.

The MarkdownKB UI shows a banner when no API key is configured and the server is network-exposed. This is the situation that needs a key.

## What Does It Protect?

The API key protects all `/api/v1/*` endpoints except `/api/v1/health`. This includes:

- **Reading:** search, chat, file content, knowledge graph queries
- **Writing:** index files, create buckets, update tags, save documents
- **Deleting:** unindex files, delete buckets, clear databases
- **MCP:** Streamable HTTP transport connections (stdio is local-only and doesn't need auth)

Without a key, all of these are open to anyone who can reach the server.

## How to Set a Key

### Option 1: Docker Secret (recommended)

```bash
make secrets-init   # create secrets/ dir if it doesn't exist yet

# Generate a random key
openssl rand -hex 16 > secrets/markdownkb_api_key

# Or set your own
echo -n "your-chosen-key" > secrets/markdownkb_api_key
```

Restart the container: `make restart`

### Option 2: Environment Variable

In `.env`:

```
MARKDOWNKB_API_KEY=your-key-here
```

Then `make docker-down && make docker-up`.

### Option 3: Generate from the UI

When the setup banner appears, click "Generate API Key". This creates a key, saves it to `secrets/markdownkb_api_key`, and configures the current browser session automatically. Copy the key — it won't be shown again.

Key generation is restricted to localhost — the request must come from the same machine running MarkdownKB. This prevents a LAN attacker from racing to set the key on a network-exposed instance.

## Using the Key

### Browser

The MarkdownKB web UI stores the key in localStorage after you set it. No manual header needed.

### REST API

Include the key in the `X-MarkdownKB-Key` header:

```bash
curl -H "X-MarkdownKB-Key: your-key" http://localhost:9713/api/v1/search \
  -d '{"query": "authentication"}'
```

### MCP (Streamable HTTP)

Two options:

**Bearer token:** `Authorization: Bearer your-key` (preferred — not written to access logs)

**Custom header:** `X-MarkdownKB-Key: your-key`

### MCP (stdio transport)

Not applicable — stdio runs locally and doesn't use HTTP.

## What Happens Without a Key

- All endpoints are open (no authentication)
- The UI shows a warning banner when network-exposed
- Everything works — the key is optional but recommended for network use

## Key Rotation

To change the key, update the secrets file or environment variable and restart. Active browser sessions using the old key will get 401 errors — users need to enter the new key.

## Security Recommendations

- Use Docker secrets (file-based) over environment variables — env vars are visible in `docker inspect`
- Generate a random key (`openssl rand -hex 16`) rather than choosing one
- If exposing MarkdownKB on a network, also consider HTTPS via a reverse proxy (nginx, Caddy)
- The API key is a shared secret, not per-user auth — all users share the same key
