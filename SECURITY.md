# Security

mdkb handles API keys, accesses the file system, and optionally executes terminal commands. This document describes the security model and how to report issues.

## Sensitive Data

- **API keys** are stored in `config/settings.yaml` (gitignored) and optionally in `.env` (gitignored). They are never logged or exposed via API responses.
- **No authentication** — mdkb is designed for local/trusted-network use. Do not expose it to the public internet without adding an auth layer.

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

## Rate Limiting

Optional rate limiting via slowapi can be enabled with the `rate_limiting` feature flag to prevent API abuse.

## Reporting Vulnerabilities

If you discover a security vulnerability, please open a GitHub issue or contact the maintainer directly. Include steps to reproduce and the expected vs. actual behavior.
