# Security

MarkdownKB handles API keys, accesses the file system, and optionally executes terminal commands. This document describes the security model and how to report issues.

## Sensitive Data

- **API keys** are stored in Docker secret files (`secrets/`) or environment variables — never in `config/settings.yaml`. They are never logged or exposed via API responses.

## Authentication

MarkdownKB supports optional API key authentication via the `X-MarkdownKB-Key` header:

- Set via Docker secret (`secrets/markdownkb_api_key`) or the `MARKDOWNKB_API_KEY` environment variable.
- When configured, all `/api/*` endpoints (except `/api/health`) require the header. Missing or invalid keys return **401 Unauthorized**.
- When empty (default), authentication is disabled — suitable for local/single-user use.
- **If exposing MarkdownKB to a network, always set an API key.** Without it, destructive endpoints (clear databases, change LLM provider, rewrite system prompt) are fully open.

### MCP Server Authentication

The standalone MCP server uses the same API key. When `MARKDOWNKB_API_KEY` is configured, the MCP server requires authentication via either:

- **Header:** `X-MarkdownKB-Key: <key>` (same as the REST API)
- **Query parameter:** `?token=<key>` (for clients that pass tokens via URL)

The stdio transport is never authenticated (stdio is process-local and not network-accessible). When no API key is configured, MCP connections are unauthenticated — suitable only for localhost-bound deployments.

## File System Access

- The file browser reads files under configured `sources` directories only.
- In Docker, only explicitly mounted source directories are accessible — the container does not mount the entire home directory.
- Sources with `writable: false` reject writes via the API and MCP tools (403).
- File paths provided to API endpoints are validated to prevent directory traversal.

## Feature Flags

Security-sensitive features are disabled by default and must be explicitly enabled in `config/settings.yaml`:

| Feature | Default | Risk |
|---------|---------|------|
| `mcp.save_document` | `false` | MCP clients can write/delete markdown files in writable source directories |
| `mcp.allow_bucket_writes` | `false` | MCP clients can create/delete/push to ephemeral buckets even when `read_only: true` |
| `write_api` plugin | `false` | Create/update/delete markdown files via HTTP |
| `sources[].writable` | `true` | Per-source write protection — set `false` to block writes to that directory |

The `mcp.read_only` flag (default `true`) blocks all MCP write tools regardless of individual flags. `allow_bucket_writes` is a narrow exemption that keeps the main knowledge base read-only while allowing bucket operations — useful when giving agents write access for scratch/research workflows without granting access to curated documents.

The `write_api` plugin and MCP write tools validate paths to prevent directory traversal, restrict writes to configured source directories only, check the per-source `writable` flag (403 if read-only), and verify the directory is accessible on disk (422 if not mounted). Overwrites require an explicit `overwrite: true` flag.

## Rate Limiting

Optional rate limiting via slowapi can be enabled with the `rate_limiting` feature flag to prevent API abuse.

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it privately — **do not open a public GitHub issue**. Email the maintainer directly with steps to reproduce and the expected vs. actual behavior. This gives us time to prepare a fix before the issue is disclosed publicly.
