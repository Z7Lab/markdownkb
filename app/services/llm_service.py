"""LLM service functions: model discovery, connection testing."""

import logging
import time

import anthropic
import httpx
import openai

from app.text import parse_model as _parse_model
from app.security import validate_api_base

logger = logging.getLogger(__name__)


# ── Model Discovery ───────────────────────────────────────


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

    # Fall back to the standard OpenAI /v1/models endpoint
    if api_base:
        models = _fetch_openai_models(api_base)
        if models:
            return models, f"Found {len(models)} model(s)"
        return [], f"Could not fetch models from {api_base}/v1/models"

    return [], "No models available for this provider"


def _fetch_openai_models(api_base: str) -> list[dict]:
    """Query /v1/models on an OpenAI-compatible server."""
    try:
        validate_api_base(api_base)
        url = f"{api_base.rstrip('/')}/models"
        if "/v1" not in url:
            url = f"{api_base.rstrip('/')}/v1/models"
        resp = httpx.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        models = data.get("data", [])
        return [
            {"id": f"openai/{m['id']}", "label": m["id"]}
            for m in models
            if isinstance(m, dict) and "id" in m
        ]
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.warning("Failed to fetch models from %s: %s", api_base, e)
        return []


# ── Connection Testing ────────────────────────────────────

def test_ollama(api_base: str) -> str:
    """Test connectivity to an Ollama instance."""
    try:
        validate_api_base(api_base)
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


def test_api_provider(model: str, api_base: str, api_key: str = "") -> dict:
    """Test connectivity to an API-based LLM provider.

    Returns a dict with keys: ``ok`` (bool), ``message`` (str), and
    optionally ``reply`` (the model's response text).
    """
    try:
        validate_api_base(api_base)
    except ValueError as e:
        return {"ok": False, "message": f"Invalid api_base: {e}"}

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
                max_tokens=32,
                temperature=0,
            )
            msg = response.choices[0].message
            reply = (msg.content or "").strip()
            # Some models (Gemma 4, DeepSeek) put output in reasoning_content
            if not reply:
                reasoning = getattr(msg, "reasoning_content", None) or ""
                if reasoning.strip():
                    reply = "(thinking model responded)"

        if reply:
            return {"ok": True, "message": f"Connected. Response: {reply}", "reply": reply}
        return {"ok": True, "message": "Connected (model returned empty response)", "reply": ""}
    except (
        anthropic.APIError, anthropic.APIConnectionError,
        anthropic.AuthenticationError, anthropic.APITimeoutError,
        openai.APIError, openai.APIConnectionError,
        openai.AuthenticationError, openai.APITimeoutError,
        RuntimeError, OSError, ValueError,
    ) as e:
        return {"ok": False, "message": f"Connection failed: {e}"}


def test_llm_connection(
    provider_name: str, model: str, api_base: str, api_key: str = "",
) -> dict:
    """Test connectivity to an LLM provider.

    Returns a dict with keys: ``ok`` (bool), ``message`` (str).
    """
    if not model:
        return {"ok": False, "message": "No model configured."}

    provider_type, _ = _parse_model(model)
    if ("ollama" in provider_name.lower() or provider_type == "ollama") and api_base:
        msg = test_ollama(api_base)
        ok = not msg.startswith(("Cannot reach", "Connection failed", "Connection error"))
        return {"ok": ok, "message": msg}

    return test_api_provider(model, api_base, api_key)


def ping_model(model: str, api_base: str, api_key: str = "") -> dict:
    """Quick test that a specific model loads and responds.

    Returns a dict with keys: ``ok`` (bool), ``message`` (str).
    """
    if not model:
        return {"ok": False, "message": "No model configured."}
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
    """Fetch model capabilities from plugin catalogs, merged with profile data."""
    from app.config.profiles import get_profile
    from app.config._paths import DEFAULT_CONFIG_PATH

    profile = get_profile(model, config_dir=DEFAULT_CONFIG_PATH.parent)
    profile_dict = {"profile": profile.to_dict()}

    catalog_info = _get_catalog_model_info(model, api_base)
    if catalog_info:
        return {**catalog_info, **profile_dict}

    return profile_dict


# ── Test Prompt (streaming) ────────────────────────────────

def stream_test_prompt(
    prompt: str,
    model: str,
    api_base: str,
    temperature: float,
    max_tokens: int,
    api_key: str = "",
    extra_body: dict | None = None,
):
    """Stream a raw prompt to the model, yielding (event, data) tuples.

    Think blocks are buffered and stripped before yielding content tokens.
    """
    from app.rag.llm import strip_thinking as _strip_thinking

    validate_api_base(api_base)
    provider_type, model_name = _parse_model(model)
    start = time.time()
    token_count = 0

    def _buffer_and_yield(raw_chunks):
        """Buffer until think block is resolved, then passthrough."""
        buffer = ""
        passthrough = False
        for text in raw_chunks:
            if passthrough:
                yield text
                continue
            buffer += text
            if buffer.lstrip().startswith("<think") and "</think>" not in buffer:
                continue
            if "</think>" in buffer:
                cleaned = _strip_thinking(buffer)
                if cleaned:
                    yield cleaned
                passthrough = True
                continue
            yield buffer
            passthrough = True
        if not passthrough and buffer:
            cleaned = _strip_thinking(buffer)
            if cleaned:
                yield cleaned

    try:
        if provider_type == "anthropic":
            client = anthropic.Anthropic(api_key=api_key or "")
            with client.messages.stream(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            ) as stream:
                for text in _buffer_and_yield(stream.text_stream):
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
            if extra_body:
                create_kwargs["extra_body"] = extra_body

            response = client.chat.completions.create(**create_kwargs)

            def _openai_chunks():
                for chunk in response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        yield delta.content

            for text in _buffer_and_yield(_openai_chunks()):
                token_count += 1
                yield "token", {"content": text}

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
