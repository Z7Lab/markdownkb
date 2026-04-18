# Model Profiles

YAML files in this directory define per-model-family configuration.
Files are matched by glob pattern against the model name (provider prefix stripped).

Files here take priority over built-in profiles. Use them to override defaults
or add profiles for models not covered by the built-ins.

## Fields

| Field | Values | Default | Description |
|---|---|---|---|
| `pattern` | glob string | required | Matched against model name, e.g. `my-model*` |
| `thinking_format` | `none` `reasoning_content` `xml_tags` | `none` | How the model exposes chain-of-thought |
| `default_max_tokens` | integer | `4096` | Suggested max output tokens |
| `default_temperature` | float | `0.3` | Suggested temperature |
| `context_managed_by` | `server` `api` `provider` | `server` | Who controls the context window |
| `max_context` | integer or null | `null` | Context window size (for display) |
| `notes` | string | `""` | Shown in the UI below model info badges |

### `thinking_format` values
- `none` — no chain-of-thought, use content as-is
- `reasoning_content` — thinking arrives in a separate `reasoning_content` field (DeepSeek R-series, Gemma 4)
- `xml_tags` — thinking is wrapped in `<think>...</think>` tags inside content (QwQ, Qwen3)

### `context_managed_by` values
- `server` — context set on the server (llama.cpp `--ctx-size`, LM Studio)
- `api` — context passed in the API call (Ollama `num_ctx`)
- `provider` — managed by the cloud provider, not configurable

## Example

```yaml
pattern: "my-custom-model*"
thinking_format: xml_tags
default_max_tokens: 8192
default_temperature: 0.6
context_managed_by: server
max_context: 65536
notes: "Custom model with chain-of-thought via XML tags."
```
