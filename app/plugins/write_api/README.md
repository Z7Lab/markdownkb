# Write API Plugin

HTTP endpoint for creating, updating, and deleting markdown documents in watched source directories. Files are automatically picked up by the file watcher for indexing.

**Feature flag:** `write_api`
**Prefix:** `/api/documents`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/documents` | Create or update a markdown document |
| DELETE | `/api/documents` | Delete a markdown document |

## Create/Update

```json
{
  "path": "notes/idea.md",
  "content": "# My Idea\n\nContent here...",
  "source": "",
  "overwrite": false
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `path` | (required) | Relative path within source directory (must end in `.md`) |
| `content` | (required) | Markdown content to write |
| `source` | first configured source | Target source directory (must be a configured source) |
| `overwrite` | `false` | Allow overwriting existing files (409 if file exists and `false`) |

## Delete

Query parameters: `path` (required), `source` (optional, defaults to first source).

## Security

- Path traversal (`..`) is rejected
- Only `.md` files are allowed
- Target must be a configured source directory
- Unsafe filename characters are rejected
- Defaults to off (`write_api: false`)

## Versioning

Every successful write or delete is auto-committed to the per-source managed git repo (unless the source has `versioned: false` or `versioning.enabled: false`). The response includes a `version_commit` field with the new commit SHA, or `null` when versioning is not active for the target source. See [docs/explanation/versioning.md](../../../docs/explanation/versioning.md) for background and [docs/reference/configuration.md#versioning](../../../docs/reference/configuration.md#versioning) for the config surface.

## Dependencies

- `app.config.Settings` — source directory validation
- `app.versioning.GitManager` (via `app.state.versioning_manager`) — best-effort auto-commit, never blocks the write
