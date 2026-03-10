"""LLM service functions: model discovery, connection testing."""

import logging
import time

import litellm
import httpx

logger = logging.getLogger(__name__)


# ── Model Discovery ───────────────────────────────────────

_PROVIDER_PREFIX_MAP = {
    "anthropic": "anthropic",
    "openai": "openai",
    "groq": "groq",
    "deepseek": "deepseek",
    "mistral": "mistral",
    "gemini": "gemini",
    "xai": "xai",
    "together": "together_ai",
    "fireworks": "fireworks_ai",
    "perplexity": "perplexity",
    "cerebras": "cerebras",
    "openrouter": "openrouter",
}

_OPENAI_CHAT_PREFIXES = ("gpt-", "o1", "o3", "o4", "chatgpt-")


def get_provider_models(provider_name: str) -> list[str]:
    """Return known chat models for API-based providers via LiteLLM registry."""
    name = provider_name.lower()
    for key, litellm_key in _PROVIDER_PREFIX_MAP.items():
        if key in name:
            models = sorted(litellm.models_by_provider.get(litellm_key, set()))
            if litellm_key == "openai":
                models = [m for m in models
                          if any(m.startswith(p) for p in _OPENAI_CHAT_PREFIXES)]
            prefix = litellm_key + "/"
            return [m if m.startswith(prefix) else f"{prefix}{m}" for m in models]
    return []


def _get_plugin_catalog(provider_name: str, api_base: str = "") -> list[dict] | None:
    """Check if a plugin catalog provides model entries for this provider."""
    try:
        from app.plugins.catalogs import get_catalog
        mod = get_catalog(provider_name)
        if mod and hasattr(mod, "get_model_entries"):
            import inspect
            sig = inspect.signature(mod.get_model_entries)
            if "api_base" in sig.parameters:
                return mod.get_model_entries(api_base=api_base)
            return mod.get_model_entries()
    except ImportError:
        pass
    return None


def _ids_to_entries(ids: list[str]) -> list[dict]:
    """Convert plain model ID strings to {id, label} dicts."""
    return [{"id": m, "label": m} for m in ids]


def build_model_list(
    provider_name: str, api_base: str,
) -> tuple[list[dict], str]:
    """Fetch and return model list as {id, label} entries with status message."""
    # Check plugin catalogs first (returns rich {id, label} entries)
    catalog = _get_plugin_catalog(provider_name, api_base)
    if catalog:
        return catalog, f"Found {len(catalog)} model(s)"

    # Fall back to LiteLLM's built-in registry for other providers
    known = get_provider_models(provider_name)
    if known:
        return _ids_to_entries(known), f"Found {len(known)} known model(s)"
    return [], "No models available for this provider"


# ── Connection Testing ────────────────────────────────────

def test_ollama(api_base: str) -> str:
    """Test connectivity to an Ollama instance."""
    try:
        resp = httpx.get(
            f"{api_base.rstrip('/')}/api/tags", timeout=10,
        )
    except httpx.ConnectError:
        return (
            f"Cannot reach {api_base}\n"
            "Try: OLLAMA_HOST=0.0.0.0 ollama serve"
        )
    except httpx.HTTPError as e:
        return f"Connection error: {e}"

    if resp.status_code != 200:
        return f"Connection failed: HTTP {resp.status_code}"

    data = resp.json()
    models = [m["name"] for m in data.get("models", [])]
    if models:
        return (
            f"Connected to {api_base}\n"
            f"Available models: {', '.join(models)}"
        )
    return (
        f"Connected to {api_base} but no models found. "
        "Pull a model first."
    )


def test_api_provider(model: str, api_base: str, api_key: str = "") -> str:
    """Test connectivity to an API-based LLM provider."""
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": "Say OK"}],
        "max_tokens": 16,
        "temperature": 0,
    }
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key

    try:
        response = litellm.completion(**kwargs)
        reply = (response.choices[0].message.content or "").strip()
        if reply:
            return f"Connected. Response: {reply}"
        return "Connected (model returned empty response)"
    except (
        litellm.APIError, litellm.APIConnectionError,
        litellm.Timeout, litellm.AuthenticationError,
        RuntimeError, OSError, ValueError,
    ) as e:
        return f"Connection failed: {e}"


def test_llm_connection(
    provider_name: str, model: str, api_base: str, api_key: str = "",
) -> str:
    """Test connectivity to an LLM provider."""
    if not model:
        return "No model configured."

    if "ollama" in provider_name.lower() and api_base:
        return test_ollama(api_base)

    return test_api_provider(model, api_base, api_key)


def ping_model(model: str, api_base: str, api_key: str = "") -> str:
    """Quick test that a specific model loads and responds."""
    if not model:
        return "No model configured."
    return test_api_provider(model, api_base, api_key)


# ── Model Capabilities ────────────────────────────────────

def _get_catalog_model_info(model: str, api_base: str = "") -> dict | None:
    """Query all plugin catalogs for model info."""
    try:
        from app.plugins.catalogs import get_catalog
        import inspect
        from pathlib import Path

        catalogs_dir = Path(__file__).resolve().parent.parent / "plugins" / "catalogs"
        for child in catalogs_dir.iterdir():
            if not child.is_dir() or child.name.startswith("_"):
                continue
            mod = get_catalog(child.name)
            if mod and hasattr(mod, "get_model_info"):
                sig = inspect.signature(mod.get_model_info)
                if "api_base" in sig.parameters:
                    info = mod.get_model_info(model, api_base=api_base)
                else:
                    info = mod.get_model_info(model)
                if info:
                    return info
    except ImportError:
        pass
    return None


def get_model_capabilities(model: str, api_base: str = "") -> dict:
    """Fetch model capabilities from plugin catalogs, then LiteLLM as fallback."""
    # Try plugin catalogs first — they have the richest data
    catalog_info = _get_catalog_model_info(model, api_base)
    if catalog_info:
        return catalog_info

    # Fall back to LiteLLM's built-in model registry
    result: dict = {}
    try:
        info = litellm.get_model_info(model)
        result = {
            "max_input_tokens": info.get("max_input_tokens"),
            "max_output_tokens": info.get("max_output_tokens"),
            "input_cost_per_token": info.get("input_cost_per_token"),
            "output_cost_per_token": info.get("output_cost_per_token"),
            "supports_vision": info.get("supports_vision", False),
            "supports_function_calling": info.get("supports_function_calling", False),
            "supports_response_schema": info.get("supports_response_schema", False),
            "supports_pdf_input": info.get("supports_pdf_input", False),
            "litellm_provider": info.get("litellm_provider", ""),
            "mode": info.get("mode", ""),
        }
    except Exception as e:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.info("Could not fetch model info for %s: %s", model, e)

    if not result:
        result["error"] = "No model info available"
    return result


# ── Test Prompt (streaming) ────────────────────────────────

def stream_test_prompt(
    prompt: str,
    model: str,
    api_base: str,
    temperature: float,
    max_tokens: int,
    api_key: str = "",
    num_ctx: int | None = None,
):
    """Stream a raw prompt to the model, yielding (event, data) tuples."""
    kwargs: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key
    if num_ctx:
        kwargs["num_ctx"] = num_ctx

    start = time.time()
    token_count = 0

    try:
        response = litellm.completion(**kwargs)
    except (
        litellm.APIError, litellm.APIConnectionError,
        litellm.Timeout, litellm.AuthenticationError,
        RuntimeError, OSError, ValueError,
    ) as e:
        yield "error", {"message": str(e)}
        return

    for chunk in response:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            token_count += 1
            yield "token", {"content": delta.content}

    elapsed = time.time() - start
    yield "done", {
        "model": model,
        "time_seconds": round(elapsed, 2),
        "chunks": token_count,
    }
