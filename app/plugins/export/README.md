# Export Plugin

Conversation export in markdown or JSON format.

**Feature flag:** `export`
**Prefix:** `/api`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/export` | Export conversations as markdown or JSON |

## Request Body

```json
{
  "format": "markdown"
}
```

Format options: `"markdown"` or `"json"`.

## Dependencies

- `app.services.chat_service` — conversation history access
