# Changelog

All notable changes to MarkdownKB are documented here.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Every release MUST include a "Breaking changes" section. Write **none** if there are none.

## [Unreleased]

### Added
- Full-state backup and restore (Settings → Backup & Restore). Exports databases, vector store, plugin data, and optionally configuration as a single `.tar.gz`. Restore is staged with atomic swap and a restart-required marker. See [Backup and Restore](docs/how-to/backup-and-restore.md).
- Update detection via PyPI / GitHub releases (Settings → About). Off by default; user opts in via the `update_check` core flag. No background polling. See [Versioning and Upgrades](docs/explanation/versioning-and-upgrades.md).
- Canonical schema-migration runner at `app/storage/migrations.py` (`PRAGMA user_version` + ordered migration list). Retrofitted scopedb, bucketdb, plandb, presetsdb to use it.
- Single source of truth for the running version (`app/version.py`, read from `pyproject.toml` / installed metadata).
- Per-key MCP rate limiting (`mcp.rate_limit_per_minute` in settings; Settings → MCP → Rate limit). Sliding-window in-process limiter, off by default.
- Docker deployment guide (`docs/how-to/docker-deployment.md`) and `Dockerfile.example` for extending the base image with extras (OCR, PDF, custom packages).

### Fixed
- Dashboard now scrolls when content overflows (was clipped because `flex-1` had no parent flex context).
- Built-in docs bucket no longer rebuilds on every Docker rebuild — hash now uses file content, not mtime, which Docker resets on every `--no-cache` build.
- MCP server's DNS rebinding protection no longer rejects legitimate LAN/Docker-bridge clients with `400 Invalid Host header`. Default allowlist is seeded with localhost, host.docker.internal, hostname, LAN IPs, and the explicit `--host` IP.

### Changed
- `ConfirmDialog` description now accepts `React.ReactNode` (was `string`).

### Breaking changes
- none.

---

## Release checklist (template — copy into release commit)

1. Bump `project.version` in `pyproject.toml`.
2. Move items from `[Unreleased]` into a new section: `## [X.Y.Z] - YYYY-MM-DD`.
3. Confirm every new schema column ships with a `_MIGRATIONS` entry.
4. Confirm any plugin manifest changes still satisfy `mdkb_min` / `mdkb_max`.
5. Run the upgrade test: boot the previous version, perform realistic operations, upgrade to this version, assert all data intact.
6. Tag and push; CI builds the Docker image and pushes to the registry as `latest`.
