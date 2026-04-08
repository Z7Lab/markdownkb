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
4. Copies to `{data_directory}/plugins/<name>/`
5. Adds `plugins.<name>.enabled: false` to settings
6. **Requires a container restart** to activate

External plugins persist across container rebuilds via the Docker named volume (or bind mount).

To uninstall: `DELETE /api/plugins/{name}` (only works for external plugins).

## Validation Rules

A valid plugin must have:

1. `__init__.py` with `FEATURE_FLAG` (string) and `router` (APIRouter)
2. The `FEATURE_FLAG` must match the plugin directory name
3. `plugin.yaml` is recommended but not required

## Plugin-Owned Databases

Plugins that need persistent storage should create their own SQLite database in `on_startup` and store the instance on `app.state`. Follow the pattern used by tags, buckets, and knowledge_graph:

```python
def on_startup(app) -> None:
    from .my_db import MyDB
    settings = app.state.settings
    db = MyDB(settings.data_directory)  # creates {data_directory}/my_plugin.db
    app.state.my_db = db

def on_shutdown(app) -> None:
    db = getattr(app.state, "my_db", None)
    if db:
        db.close()
```

Access in your router via `request.app.state.my_db`. Do not use `app/deps.py` — that's for core dependencies. Plugin resources live on `app.state` and are accessed directly.

## MCP Tool Integration

Plugins can provide MCP tools. Create tool files in `app/mcp/tools/` with `requires_plugin` set to your plugin name:

```python
# app/mcp/tools/my_tool.py
TOOL = {
    "name": "my_tool",
    "feature_flag": None,
    "requires_plugin": "my_plugin",
}

_mcp = None  # Injected by register_tools()

def handler(query: str) -> dict:
    """Description shown to MCP clients."""
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    # Access plugin resources from MCP lifespan context
    my_db = deps.get("my_db")
    ...
```

When your plugin is disabled, the MCP tool is automatically excluded from registration. If your plugin owns a database, you also need to initialize it in the MCP server's lifespan (`mcp_server.py`) — the MCP server runs as a separate process and doesn't share `app.state` with the FastAPI app.

## Background Processing

For long-running operations, use a background thread with module-level status tracking. Follow the pattern used by the knowledge_graph extraction runner:

```python
import threading

_status = {"running": False, "progress": 0.0, "message": "", "result": ""}
_lock = threading.Lock()

def _bg_work(args):
    try:
        # ... do work, update _status with _lock ...
        pass
    finally:
        with _lock:
            _status["running"] = False

@router.post("/my-plugin/start")
def start(request: Request):
    with _lock:
        if _status["running"]:
            raise HTTPException(409, "Already running")
        _status["running"] = True
        _status["cancel"] = threading.Event()
    threading.Thread(target=_bg_work, daemon=True).start()
    return {"status": "started"}

@router.get("/my-plugin/status")
def status(request: Request):
    with _lock:
        return dict(_status)
```

The frontend polls the status endpoint and shows progress. See `knowledge_graph/router.py` for the full pattern with cancellation support.

## README Convention

Every plugin should have a `README.md` in its directory. This is for developers browsing the source — it's not shown in the UI. Cover:

- What the plugin does
- Prerequisites (system dependencies, other plugins)
- Endpoints
- MCP tools (if any)
- Configuration options
- Storage (databases, caches)

## Categories

The `category` field in `plugin.yaml` determines how plugins are grouped in the Settings UI:

| Category | Use for |
|----------|---------|
| `core` | Essential functionality (tags, buckets) |
| `search` | Search and discovery features |
| `ai` | LLM-powered features (planner) |
| `visualization` | Graph and visualization (docmap, knowledge_graph) |
| `integration` | External system integration (converter, write_api) |
| `export` | Data export features |
| `advanced` | Power-user features |

## Reference Plugins

Study the builtin plugins as examples:

| Plugin | Complexity | Good example of |
|--------|-----------|-----------------|
| `export` | Simple | Minimal plugin — one endpoint, no config, no database |
| `write_api` | Simple | File I/O plugin, integration category |
| `tags` | Medium | Plugin-owned database, lifecycle hooks, config schema, core integration via hook registration |
| `search` | Complex | Multiple endpoints, SSE streaming, rich config schema |
| `docmap` | Complex | Background computation with caching and progress, event bus integration |
| `knowledge_graph` | Complex | Plugin-owned database, background extraction with cancel, per-file operations, MCP tools |
| `converter` | Medium | System dependency declaration, background processing, no database |
| `buckets` | Complex | Plugin-owned database + service layer, ChromaDB collections, expiration/cleanup |
