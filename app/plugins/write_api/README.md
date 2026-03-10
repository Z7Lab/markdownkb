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

## Dependencies

- `app.config.Settings` — source directory validation
