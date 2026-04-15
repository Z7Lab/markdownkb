# Versioning and Upgrades

This document explains how MarkdownKB versions itself, how upgrades stay non-breaking, and how the Settings UI surfaces an "update available" signal.

It complements [Backup and Restore](../how-to/backup-and-restore.md), which is the rollback path: a backup taken before an upgrade is the guaranteed way to revert.

## The two things users need

Before MarkdownKB can be released to a wider audience, two questions must have clear answers in the product:

1. **Is a new version available?** — surfaced in the Settings UI, with a link to release notes.
2. **Will updating destroy my data?** — every release ships with forward-only schema migrations, and the upgrade flow is documented per install method.

The rest of this document covers how each of those is implemented.

## Version source of truth

The single source of truth for the running version is `pyproject.toml` (`project.version`). The FastAPI app exposes it as `app.version`, which is read by:

- `GET /api/backups/status` — included in backup manifests and the restart-required marker
- `GET /api/version` — the update-detection endpoint (see below)
- The Settings UI footer

There is no second copy in an `__init__.py` or `VERSION` file — `pyproject.toml` is authoritative.

The frontend's `package.json` version is held at `0.0.0` deliberately. The frontend is not separately versioned; it ships as part of the backend build and inherits the backend's version.

## Update detection

The `app/version_check/` module compares the running version against the latest available version for the install method. It runs on demand (when the Settings panel is opened or refreshed) — there is no background polling.

| Install method | Source                         | Comparison                                           |
| -------------- | ------------------------------ | ---------------------------------------------------- |
| Docker         | Docker Hub registry            | `latest` tag's image digest vs running image digest  |
| Native (pip)   | PyPI JSON API                  | latest released version vs `pyproject.toml` version  |
| Dev (git)      | `git rev-parse @{upstream}`    | local HEAD vs upstream tracking branch               |

The install method is auto-detected at startup:

- Presence of `/.dockerenv` and the `MARKDOWNKB_DATA_DIR` env var → Docker
- Otherwise, presence of a `.git` directory above the install → Dev
- Otherwise → Native (pip)

### Privacy and offline behaviour

Update checks are anonymous — no telemetry beyond the version-check HTTP request. They time out quickly (5 seconds) and fail silently when offline; the Settings UI shows "could not check for updates" rather than blocking.

Update checks are off by default and require explicit user opt-in via a Settings toggle. Once enabled, they run only when the user views the Settings panel — never in the background.

## Apply flow per install method

The Settings UI displays the apply command for the user's install method as plain text — it never runs the command itself. Auto-apply is explicitly out of scope.

| Install method | Apply command                          |
| -------------- | -------------------------------------- |
| Docker         | `docker compose pull && make docker-up` |
| Native (pip)   | `pip install -U markdownkb`            |
| Dev (git)      | `git pull && make install`             |

A link to the release notes (currently the GitHub releases page) appears alongside the command.

## Schema versioning

Every SQLite database in MarkdownKB uses the `PRAGMA user_version` pattern with an ordered migration list. This is the canonical pattern; any new database added to the project must follow it.

### The pattern

```python
_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS my_table (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    -- new columns added by migrations are listed here too,
    -- so fresh databases get them from the start
    extra_field TEXT
);
"""

_MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "add extra_field to my_table",
     "ALTER TABLE my_table ADD COLUMN extra_field TEXT"),
]

def _run_migrations(conn):
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    target = len(_MIGRATIONS)
    if current >= target:
        return
    for version, description, sql in _MIGRATIONS:
        if version <= current:
            continue
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            # Column already exists — fresh DB created with latest schema
            pass
    conn.execute(f"PRAGMA user_version = {int(target)}")
```

`app/storage/chatdb.py` and `app/storage/searchdb.py` are reference implementations.

### Migration discipline

- **Forward-only.** Migrations add columns or tables. They never drop columns or change types in-place. To change a column type, add a new column, backfill, and drop the old one in a later release.
- **Idempotent.** Catch `sqlite3.OperationalError` so re-runs are safe.
- **Update `_CREATE_SQL` too.** When migration N adds a column, also add it to the `CREATE TABLE` so fresh installs get it from the start.
- **Sequential numbering.** Migration versions start at 1 and have no gaps.
- **No data loss.** New columns must have a sensible default or be NULL-tolerant. Backfills happen in the migration itself or on first read.

### Plugin-owned databases

Plugins that own a database (buckets, tags, knowledge_graph) follow the same pattern. The plugin's database module owns its `_MIGRATIONS` list independently of the core schema version.

### Legacy `schema_version` table

Two existing databases (`trackingdb.py` and `knowledgegraph.py`) use an older equivalent pattern — a `schema_version` table with explicit `_migrate_v1_to_v2`-style functions. These are functionally equivalent and stay as-is; new databases must use the canonical `PRAGMA user_version` + `_MIGRATIONS` pattern via `app.storage.migrations.run_migrations`.

## Config migrations

`config/settings.yaml` is migrated at startup by `_migrate_settings` in `app/config/__init__.py`. The function tolerates legacy `features:` and flat `plugins:` layouts, normalises them to the current structured layout, and persists the result back to disk.

The same pattern applies for any future config restructure: detect the old shape, transform, save. Never error on missing new keys; supply a default.

## Plugin contract versioning

Plugins declare their compatible mdkb version range in `plugin.toml`:

```toml
[plugin]
name = "my_plugin"
mdkb_min = "1.0.0"
mdkb_max = "1.99.0"
```

At startup, the plugin loader checks compatibility. An incompatible plugin is loaded but disabled with a clear message in the Plugins panel: "requires mdkb ≥ X, you have Y".

This shifts the upgrade pain to the plugin (the plugin author bumps their declared range when they've tested) rather than silently breaking the host.

## What's out of scope

- **Auto-apply / background upgrades** — the user always consents to each upgrade.
- **Rollback** — handled by [Backup and Restore](../how-to/backup-and-restore.md). Take a backup before upgrading; restore it if the upgrade misbehaves.
- **Telemetry beyond anonymous version check** — no usage analytics, no error reporting, no machine identifiers in update requests.

## See also

- [Backup and Restore](../how-to/backup-and-restore.md) — the rollback mechanism
- [Plugin Development](../how-to/plugin-development.md) — plugin-owned schemas and the contract version range
- [Configuration](../reference/configuration.md) — settings.yaml structure
