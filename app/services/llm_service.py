"""LLM service functions: model discovery, connection testing."""

import logging
import time

import anthropic
import httpx
import openai

from app.utils import parse_model as _parse_model

logger = logging.getLogger(__name__)


# ── Model Discovery ───────────────────────────────────────


def get_provider_models(provider_name: str) -> list[str]:
    """Return known chat models for API-based providers.

    Plugin catalogs are the primary source for model lists. This function
    returns an empty list — callers should check catalogs first via
    ``build_model_list``.
    """
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
    provider_type, model_name = _parse_model(model)

    try:
        if provider_type == "anthropic":
            client = anthropic.Anthropic(api_key=api_key or "")
            response = client.messages.create(
                model=model_name,
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=16,
                temperature=0,
            )
            reply = (response.content[0].text if response.content else "").strip()
        else:
            client_kwargs: dict = {"api_key": api_key or "not-needed"}
            if api_base:
                base = api_base.rstrip("/")
                if provider_type == "ollama" and not base.endswith("/v1"):
                    base += "/v1"
                client_kwargs["base_url"] = base
            client = openai.OpenAI(**client_kwargs)
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=16,
                temperature=0,
            )
            reply = (response.choices[0].message.content or "").strip()

        if reply:
            return f"Connected. Response: {reply}"
        return "Connected (model returned empty response)"
    except (
        anthropic.APIError, anthropic.APIConnectionError,
        anthropic.AuthenticationError, anthropic.APITimeoutError,
        openai.APIError, openai.APIConnectionError,
        openai.AuthenticationError, openai.APITimeoutError,
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
    """Fetch model capabilities from plugin catalogs."""
    catalog_info = _get_catalog_model_info(model, api_base)
    if catalog_info:
        return catalog_info

    return {"error": "No model info available"}


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
    provider_type, model_name = _parse_model(model)
    start = time.time()
    token_count = 0

    try:
        if provider_type == "anthropic":
            client = anthropic.Anthropic(api_key=api_key or "")
            with client.messages.stream(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            ) as stream:
                for text in stream.text_stream:
                    token_count += 1
                    yield "token", {"content": text}
        else:
            client_kwargs: dict = {"api_key": api_key or "not-needed"}
            if api_base:
                base = api_base.rstrip("/")
                if provider_type == "ollama" and not base.endswith("/v1"):
                    base += "/v1"
                client_kwargs["base_url"] = base
            client = openai.OpenAI(**client_kwargs)

            create_kwargs: dict = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            if num_ctx is not None:
                create_kwargs["extra_body"] = {"num_ctx": num_ctx}

            response = client.chat.completions.create(**create_kwargs)
            for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    token_count += 1
                    yield "token", {"content": delta.content}

    except (
        anthropic.APIError, anthropic.APIConnectionError,
        anthropic.AuthenticationError, anthropic.APITimeoutError,
        openai.APIError, openai.APIConnectionError,
        openai.AuthenticationError, openai.APITimeoutError,
        RuntimeError, OSError, ValueError,
    ) as e:
        logger.error("LLM provider error: %s", e)
        yield "error", {"message": "LLM request failed. Check server logs for details."}
        return

    elapsed = time.time() - start
    yield "done", {
        "model": model,
        "time_seconds": round(elapsed, 2),
        "chunks": token_count,
    }
