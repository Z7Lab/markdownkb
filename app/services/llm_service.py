"""LLM service functions: model discovery, connection testing."""

import logging
import time

import litellm
import httpx

logger = logging.getLogger(__name__)


# ── Model Discovery ───────────────────────────────────────

def fetch_ollama_models(api_base: str) -> list[str]:
    """Fetch available models from an Ollama instance."""
    try:
        resp = httpx.get(
            f"{api_base.rstrip('/')}/api/tags", timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except httpx.HTTPError as e:
        logger.debug("Failed to fetch Ollama models from %s: %s", api_base, e)
    return []


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


def build_model_list(
    provider_name: str, api_base: str,
) -> tuple[list[str], str]:
    """Fetch and return model list with status message."""
    if "ollama" in provider_name.lower() and api_base:
        raw = fetch_ollama_models(api_base)
        if raw:
            choices = [f"ollama/{m}" for m in raw]
            return choices, f"Found {len(raw)} model(s)"
        return [], f"No models found at {api_base}"

    known = get_provider_models(provider_name)
    if known:
        return known, f"Found {len(known)} known model(s)"
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
        "max_tokens": 5,
        "temperature": 0,
    }
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key

    try:
        response = litellm.completion(**kwargs)
        reply = response.choices[0].message.content
        if reply is None:
            logger.debug("LLM returned None content for model %s", model)
            reply = ""
        return f"Connected. Response: {reply.strip()}"
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

def get_model_capabilities(model: str, api_base: str = "") -> dict:
    """Fetch model capabilities from LiteLLM and optionally Ollama."""
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
        # LiteLLM raises bare Exception (not a subclass) for Ollama connection errors.
        logger.debug("Could not fetch model info for %s: %s", model, e)

    # Query the Ollama API directly for model details when api_base is set.
    # This works for any model served by Ollama, regardless of name prefix.
    if api_base:
        try:
            ollama_name = model.split("/", 1)[-1] if "/" in model else model
            resp = httpx.post(
                f"{api_base.rstrip('/')}/api/show",
                json={"name": ollama_name},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                details = data.get("details", {})
                result["ollama_details"] = {
                    "family": details.get("family"),
                    "parameter_size": details.get("parameter_size"),
                    "quantization_level": details.get("quantization_level"),
                    "format": details.get("format"),
                }
                # Pull context length from Ollama's model_info if LiteLLM
                # didn't provide it (e.g. remote Ollama, no local connection).
                model_info = data.get("model_info", {})
                if not result.get("max_input_tokens"):
                    for key, val in model_info.items():
                        if key.endswith(".context_length") and isinstance(val, int):
                            result["max_input_tokens"] = val
                            break
        except (httpx.HTTPError, httpx.ConnectError) as e:
            logger.debug("Failed to fetch Ollama model details for %s: %s", model, e)

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
