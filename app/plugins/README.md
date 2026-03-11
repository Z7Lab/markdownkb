# Plugins

Optional modules that extend mdkb beyond its core "chat with your docs" functionality. Each plugin is auto-discovered at startup and gated behind a feature flag — disabled plugins are never imported.

## How It Works

At startup, `app/plugins/__init__.py` scans this directory for subdirectories containing an `__init__.py`. Each valid plugin package must expose:

```python
FEATURE_FLAG: str    # Name of the feature flag in settings.yaml (e.g. "search")
router: APIRouter    # FastAPI router to register when the flag is enabled
```

The discovery/registration flow:

1. `discover_plugins()` scans `app/plugins/` for valid packages (skips `_`-prefixed dirs and `catalogs/`)
2. `register_plugins(app, settings)` imports each plugin, checks its feature flag via `settings.feature_enabled()`, and calls `app.include_router(router)` for enabled plugins
3. If a plugin fails to import (missing dependency, syntax error), it logs a warning and skips — other plugins and the core app are unaffected

## Creating a New Plugin

1. Create a directory under `app/plugins/`:
   ```
   app/plugins/my_feature/
   ├── __init__.py
   └── router.py
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
   router = APIRouter(prefix="/api/my-feature", tags=["my-feature"])

   @router.get("/example")
   def example():
       return {"hello": "world"}
   ```

4. Add the feature flag to `config/settings.yaml`:
   ```yaml
   features:
     my_feature: true
   ```

No changes to core files are needed — the plugin is picked up automatically on next startup.

## Plugin Configuration

Plugins can have their own configuration under the `plugins:` section in `settings.yaml`:

```yaml
plugins:
  search:
    chunk_multiplier: 10
    exact_phrase_matching: true
```

Access config in your plugin via `Settings.get_plugin_config("name")`. Define defaults inside your plugin:

```python
_DEFAULTS = {"chunk_multiplier": 10, "exact_phrase_matching": True}

def _cfg(settings: Settings) -> dict:
    return {**_DEFAULTS, **settings.get_plugin_config("search")}
```

A generic API is available for reading/writing any plugin's config:
- `GET /api/settings/plugins/{name}` — read config
- `PUT /api/settings/plugins/{name}` — update config (shallow merge)

## Available Plugins

| Plugin | Feature Flag | Description |
|--------|-------------|-------------|
| [search](search/) | `search` | Search with history, AI summaries, query enhancement, exact phrase matching |
| [export](export/) | `export` | Conversation export in markdown or JSON |
| [graph](graph/) | `knowledge_graph` | 3D document similarity graph visualization |
| [planner](planner/) | `mcts_planner` | MCTS-based implementation plan generation |
| [tags](tags/) | `mcp_tag_generator` | AI-powered tag generation for markdown files |
| [write_api](write_api/) | `write_api` | HTTP endpoint for creating/updating markdown documents |

**Note:** Deep Research (`deep_research` feature flag) is not a plugin — it's a shared service (`app/services/deep_research.py`) that uses the MCTS engine to provide multi-angle research synthesis. Currently consumed by the search plugin's summarize endpoint. See [docs/planner.md](../../docs/planner.md#deep-research).

## Model Catalogs

A separate plugin type lives under `catalogs/`. Catalogs provide dynamic model lists for LLM providers (populating the Settings UI dropdown). They don't use feature flags — catalogs are always active. See [catalogs/README.md](catalogs/README.md).

## Core vs Plugin Boundary

The core app provides: health, chat, threads, files, settings, embeddings, and scopes. Everything else is a plugin. Core routers are always registered in `app/api.py`. Plugins are only registered when their feature flag is enabled.
