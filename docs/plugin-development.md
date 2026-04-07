# Plugin Development

This guide covers how to build plugins for mdkb. The builtin plugins in `app/plugins/` serve as reference implementations.

## Plugin Structure

A minimal plugin is a directory with two files:

```
my_plugin/
├── __init__.py      # required — exports FEATURE_FLAG and router
├── plugin.yaml      # recommended — manifest with UI metadata
├── router.py        # convention — route handlers
└── requirements.txt # optional — extra pip dependencies
```

### `__init__.py`

Must export two names (and optionally lifecycle hooks):

```python
from .router import router

FEATURE_FLAG = "my_plugin"
__all__ = ["FEATURE_FLAG", "router", "on_startup", "on_shutdown"]

def on_startup(app) -> None:
    """Optional — called after core services are ready."""
    pass

def on_shutdown(app) -> None:
    """Optional — called before core DBs close."""
    pass
```

- `FEATURE_FLAG` — metadata identifier for the plugin (must match the directory name)
- `router` — a FastAPI `APIRouter` instance with your endpoints
- `on_startup(app)` — *(optional)* initialize plugin resources after core services are ready (e.g. create databases, register hooks)
- `on_shutdown(app)` — *(optional)* clean up plugin resources before shutdown

### `router.py`

Standard FastAPI router. Use dependency injection for settings and services:

```python
from fastapi import APIRouter, Depends, Request
from app.config import Settings
from app.deps import get_settings

router = APIRouter(prefix="/api", tags=["my-plugin"])

@router.get("/my-plugin/status")
def status(request: Request, settings: Settings = Depends(get_settings)):
    return {"ok": True}
```

### `plugin.yaml` (manifest)

The manifest tells the UI how to display and configure your plugin:

```yaml
name: my_plugin
display_name: My Plugin
description: A short description of what this plugin does.
version: 1.0.0
author: your-name
icon: puzzle                  # lucide icon name
category: integration         # core, search, ai, visualization, integration, export, mcp, advanced
feature_flag: my_plugin
requires: []                  # other feature flags this plugin depends on

endpoints:
  - method: GET
    path: /api/my-plugin/status
    description: Check plugin status

config:
  max_items:
    type: integer
    default: 50
    min: 1
    max: 1000
    label: Maximum items
    description: Maximum items to process per request
  verbose:
    type: boolean
    default: false
    label: Verbose logging
    description: Enable detailed logging output
```

**Config schema types:**

| Type | UI Control | Extra fields |
|------|-----------|--------------|
| `boolean` | Toggle switch | — |
| `integer` | Number input | `min`, `max` |
| `string` | Text input | — |

**System dependencies:**

Plugins that require external system binaries (not Python packages) can declare them in the manifest. The Settings UI checks availability and shows a warning with install instructions when dependencies are missing.

```yaml
system_dependencies:
  - name: pandoc
    binary: pandoc
    required: true
    install_hint: "apt install pandoc"
  - name: pdftotext
    binary: pdftotext
    required: false
    install_hint: "apt install poppler-utils (optional)"
```

| Field | Description |
|-------|-------------|
| `binary` | The executable name to check for on the system PATH |
| `required` | If true, the plugin cannot function without it |
| `install_hint` | Shown to the user when the dependency is missing |

The plugin should also check at runtime (e.g. `shutil.which("pandoc")`) and return clear errors from its endpoints when dependencies are missing, since the manifest check only runs when the Settings page loads.

Without a manifest, the plugin still works but appears in the UI with limited metadata (name derived from the directory, no config form).

## Plugin Configuration

Each plugin's `enabled` flag and config live together under `plugins.<name>` in `config/settings.yaml`:

```yaml
plugins:
  my_plugin:
    enabled: true
    max_items: 100
    verbose: true
```

`get_plugin_config()` automatically filters out the `enabled` key, so the standard `_cfg()` pattern works without change:

```python
_DEFAULTS = {"max_items": 50, "verbose": False}

def _cfg(settings: Settings) -> dict:
    return {**_DEFAULTS, **settings.get_plugin_config("my_plugin")}

@router.get("/my-plugin/status")
def status(request: Request, settings: Settings = Depends(get_settings)):
    cfg = _cfg(settings)
    return {"max_items": cfg["max_items"]}
```

Config is also readable/writable via the generic API:
- `GET /api/settings/plugins/my_plugin`
- `PUT /api/settings/plugins/my_plugin` (shallow merge)

## Installation

### Builtin plugins

Place the directory in `app/plugins/` and enable it in `config/settings.yaml`:

```yaml
plugins:
  my_plugin:
    enabled: true
```

### External plugins (from GitHub)

Users install external plugins through the Settings UI or the API:

```bash
curl -X POST http://localhost:9713/api/plugins/install \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/user/repo"}'
```

Accepted URL formats:
- `https://github.com/user/repo` — clones the whole repo as one plugin
- `https://github.com/user/repo/tree/main/plugins/my_plugin` — extracts a subdirectory
- `user/repo` — shorthand for GitHub

The install process:
1. Shallow-clones the repo
2. Validates `__init__.py` (must have `FEATURE_FLAG` + `router`)
3. Installs `requirements.txt` if present
4. Copies to `data/plugins/<name>/`
5. Adds `plugins.<name>.enabled: false` to settings
6. **Requires a container restart** to activate

External plugins persist across container rebuilds via the `./data:/app/data` volume mount.

To uninstall: `DELETE /api/plugins/{name}` (only works for external plugins).

## Validation Rules

A valid plugin must have:

1. `__init__.py` with `FEATURE_FLAG` (string) and `router` (APIRouter)
2. The `FEATURE_FLAG` must match the plugin directory name
3. `plugin.yaml` is recommended but not required

## Reference Plugins

Study the builtin plugins as examples:

| Plugin | Complexity | Good example of |
|--------|-----------|-----------------|
| `export` | Simple | Minimal plugin with one endpoint, no config |
| `tags` | Medium | Plugin-owned database, lifecycle hooks, core dispatcher integration |
| `search` | Complex | Multiple endpoints, SSE streaming, deep config |
| `graph` | Complex | Background computation, caching, progress events |
