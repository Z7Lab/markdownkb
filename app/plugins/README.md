# Plugins

Optional modules that extend MarkdownKB beyond its core "chat with your docs" functionality. Each plugin is auto-discovered at startup and gated by `plugins.<name>.enabled` in settings — disabled plugins are never imported.

## How It Works

At startup, `app/plugins/__init__.py` scans this directory for subdirectories containing an `__init__.py`. Each valid plugin package must expose:

```python
FEATURE_FLAG: str    # Plugin identifier (must match the directory name)
router: APIRouter    # FastAPI router to register when enabled
```

The discovery/registration flow:

1. `discover_plugins()` scans `app/plugins/` for valid packages (skips `_`-prefixed dirs and `catalogs/`)
2. `register_plugins(app, settings)` imports each plugin, checks `settings.plugin_enabled(name)`, and calls `app.include_router(router)` for enabled plugins
3. If a plugin fails to import (missing dependency, syntax error), it logs a warning and skips — other plugins and the core app are unaffected

## Creating a New Plugin

1. Create a directory under `app/plugins/`:
   ```
   app/plugins/my_feature/
   ├── __init__.py
   ├── router.py
   └── plugin.yaml
   ```

2. In `__init__.py`, expose the feature flag and router:
   ```python
   """My feature plugin — short description."""
   from app.plugins.my_feature.router import router

   FEATURE_FLAG = "my_feature"
   __all__ = ["FEATURE_FLAG", "router"]
   ```

3. In `router.py`, define your FastAPI router:
   ```python
   from fastapi import APIRouter
   router = APIRouter(prefix="/api/v1/my-feature", tags=["my-feature"])

   @router.get("/example")
   def example():
       return {"hello": "world"}
   ```

4. Add a `plugin.yaml` manifest for UI metadata:
   ```yaml
   name: my_feature
   display_name: My Feature
   description: Short description of what this plugin does.
   version: 1.0.0
   author: your-name
   icon: puzzle
   category: other
   feature_flag: my_feature
   requires: []
   endpoints:
     - method: GET
       path: /api/v1/my-feature/example
       description: Example endpoint
   config: {}
   ```

5. Enable the plugin in `config/settings.yaml`:
   ```yaml
   plugins:
     my_feature:
       enabled: true
   ```

No changes to core files are needed — the plugin is picked up automatically on next startup.

## Lifecycle Hooks

Plugins can optionally define `on_startup(app)` and `on_shutdown(app)` functions in their `__init__.py`. These are called after core services (databases, retriever, etc.) are initialized, so plugins can safely access `app.state.*`.

```python
"""My feature plugin."""
from app.plugins.my_feature.router import router

FEATURE_FLAG = "my_feature"
__all__ = ["FEATURE_FLAG", "router", "on_startup", "on_shutdown"]

def on_startup(app) -> None:
    """Initialize plugin resources (called after core services are ready)."""
    # Access app.state.settings, app.state.tracking, etc.
    pass

def on_shutdown(app) -> None:
    """Clean up plugin resources (called before core DBs close)."""
    pass
```

Use cases: creating plugin-owned databases, registering hooks with core dispatchers, running one-time migrations. See the `tags` plugin for a full example.

## Plugin Configuration

Each plugin's `enabled` flag and config live together under `plugins.<name>` in `settings.yaml`:

```yaml
plugins:
  search:
    enabled: true
    chunk_multiplier: 10
    exact_phrase_matching: true
```

`get_plugin_config()` filters out the `enabled` key, so the standard `_cfg()` pattern works cleanly:

```python
_DEFAULTS = {"chunk_multiplier": 10, "exact_phrase_matching": True}

def _cfg(settings: Settings) -> dict:
    return {**_DEFAULTS, **settings.get_plugin_config("search")}
```

A generic API is available for reading/writing any plugin's config:
- `GET /api/v1/settings/plugins/{name}` — read config
- `PUT /api/v1/settings/plugins/{name}` — update config (shallow merge)

## Available Plugins

| Plugin | Directory | Description |
|--------|-----------|-------------|
| [search](search/) | `search` | Search with history, AI summaries, query enhancement, exact phrase matching |
| [export](export/) | `export` | Conversation export in markdown or JSON |
| [graph](graph/) | `graph` | 3D document similarity graph visualization |
| [planner](planner/) | `planner` | MCTS-based implementation plan generation |
| [tags](tags/) | `tags` | Tag storage, CRUD, auto-tagging, and optional AI tag generation |
| [write_api](write_api/) | `write_api` | HTTP endpoint for creating/updating markdown documents |

**Note:** Deep Research (`core.deep_research`) is not a plugin — it's a shared service (`app/services/deep_research.py`) that uses the MCTS engine to provide multi-angle research synthesis. Its config lives under `services.deep_research`. Currently consumed by the search plugin's summarize endpoint.

## Model Catalogs

A separate plugin type lives under `catalogs/`. Catalogs provide dynamic model lists for LLM providers (populating the Settings UI dropdown). They are always active. See [catalogs/README.md](catalogs/README.md).

## Core vs Plugin Boundary

The core app provides: health, chat, threads, files, settings, embeddings, and scopes. Everything else is a plugin. Core routers are always registered in `app/api.py`. Plugins are only registered when `plugins.<name>.enabled` is true.
