# Changelog

All notable changes to MarkdownKB are documented here.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Every release MUST include a "Breaking changes" section. Write **none** if there are none.

## [Unreleased]

### Added
- Import tab — a unified content-ingestion hub for the main knowledge base: file upload (any enabled converter format), web/YouTube URL clipping, audio transcription, and create-a-markdown-note, with a destination picker for writable source directories or buckets. The same ingestion panel is reused in the Buckets tab. Conversion runs as a background job with live progress. See [UI Tabs and Plugins](docs/reference/ui-tabs-and-plugins.md).
- Audio transcription in the converter plugin — local `faster-whisper` (downloadable models, with per-segment progress) or a remote OpenAI-compatible transcription API. Local transcription requires the `full` Docker image.
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
- Runtime settings now persist in a SQLite database (`markdownkb_settings.db`). `config/settings.yaml` is read only once on first boot to seed the database; after that, configure via the Settings UI. MCP tool overrides moved from `config/mcp/*.yaml` into the settings database.
- `ConfirmDialog` description now accepts `React.ReactNode` (was `string`).

### Breaking changes
- none.
