# Model Catalogs

Dynamic model catalogs for LLM providers. Catalogs populate the model dropdown in the Settings UI and provide model metadata (pricing, context size, capabilities).

Unlike regular plugins, catalogs have no feature flag — they are always active. They also don't expose a FastAPI router. Instead, they provide functions for model discovery.

## How It Works

Each subdirectory is a catalog package with a `catalog.py` that exposes:

```python
get_model_entries(api_base?) -> list[dict]  # {id, label} for dropdown
get_model_info(id, api_base?) -> dict|None  # pricing/context/capability info
get_model_ids(api_base?) -> list[str]       # model IDs with LiteLLM prefix
```

The `api_base` parameter is optional — catalogs that need it (e.g. Ollama queries a local instance) accept it, while catalogs with a fixed endpoint (e.g. Venice) ignore it.

Catalogs are queried by `llm_service.build_model_list()` when the provider name matches the catalog directory name.

## Available Catalogs

| Catalog | Provider | Description |
|---------|----------|-------------|
| [venice](venice/) | Venice.ai | Fetches chat models from `api.venice.ai` (5-min cache) |
| [ollama](ollama/) | Ollama | Fetches models from local Ollama instance via `/api/tags` (30s cache) |

## Creating a New Catalog

1. Create a directory: `app/plugins/catalogs/my_provider/`
2. Add an empty `__init__.py`
3. Create `catalog.py` with the three required functions
4. The catalog is automatically picked up when the provider name contains the directory name
