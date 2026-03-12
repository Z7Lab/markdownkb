# Security

mdkb handles API keys, accesses the file system, and optionally executes terminal commands. This document describes the security model and how to report issues.

## Sensitive Data

- **API keys** are stored in Docker secret files (`secrets/`) or environment variables — never in `config/settings.yaml`. They are never logged or exposed via API responses.

## Authentication

mdkb supports optional API key authentication via the `X-MDKB-Key` header:

- Set via Docker secret (`secrets/mdkb_api_key`) or the `MDKB_API_KEY` environment variable.
- When configured, all `/api/*` endpoints (except `/api/health`) require the header. Missing or invalid keys return **401 Unauthorized**.
- When empty (default), authentication is disabled — suitable for local/single-user use.
- **If exposing mdkb to a network, always set an API key.** Without it, destructive endpoints (clear databases, change LLM provider, rewrite system prompt) are fully open.

## File System Access

- The file browser reads files under configured `sources` directories.
- The MCP filesystem tool (disabled by default) can browse and read arbitrary paths. Enable only on trusted networks.
- File paths provided to API endpoints are validated to prevent directory traversal.

## Terminal Execution

- The MCP terminal tool (disabled by default) executes shell commands with an allowlist of safe commands.
- **Do not enable `mcp_terminal` on untrusted networks.** It is intended for local development use.

## Feature Flags

Security-sensitive features are disabled by default and must be explicitly enabled in `config/settings.yaml`:

| Feature | Default | Risk |
|---------|---------|------|
| `mcp_filesystem` | `false` | File system read access |
| `mcp_terminal` | `false` | Shell command execution |
| `mcp_tag_generator` | `false` | File modification (creates backups) |
| `write_api` | `false` | Create/update/delete markdown files via HTTP |

The `write_api` plugin validates paths to prevent directory traversal and restricts writes to configured source directories only. It requires an explicit `overwrite: true` flag to replace existing files.

## Rate Limiting

Optional rate limiting via slowapi can be enabled with the `rate_limiting` feature flag to prevent API abuse.

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it privately — **do not open a public GitHub issue**. Email the maintainer directly with steps to reproduce and the expected vs. actual behavior. This gives us time to prepare a fix before the issue is disclosed publicly.
