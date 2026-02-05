"""LLM service functions: model discovery, connection testing."""

import logging

import litellm
import requests

logger = logging.getLogger(__name__)


def fetch_ollama_models(api_base: str) -> list[str]:
    """Fetch available models from an Ollama instance."""
    try:
        resp = requests.get(
            f"{api_base.rstrip('/')}/api/tags", timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except requests.RequestException:
        pass
    return []


def test_ollama(api_base: str) -> str:
    """Test connectivity to an Ollama instance."""
    try:
        resp = requests.get(
            f"{api_base.rstrip('/')}/api/tags", timeout=10,
        )
    except requests.ConnectionError:
        return (
            f"Cannot reach {api_base}\n"
            "Try: OLLAMA_HOST=0.0.0.0 ollama serve"
        )
    except requests.RequestException as e:
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


def test_api_provider(model: str, api_base: str) -> str:
    """Test connectivity to an API-based LLM provider."""
    litellm.drop_params = True
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": "Say OK"}],
        "max_tokens": 5,
        "temperature": 0,
    }
    if api_base:
        kwargs["api_base"] = api_base

    try:
        response = litellm.completion(**kwargs)
        reply = response.choices[0].message.content or ""
        return f"Connected. Response: {reply.strip()}"
    except (
        litellm.APIError, litellm.APIConnectionError,
        litellm.Timeout, litellm.AuthenticationError,
        RuntimeError, OSError, ValueError,
    ) as e:
        return f"Connection failed: {e}"


def test_llm_connection(
    provider_name: str, model: str, api_base: str,
) -> str:
    """Test connectivity to an LLM provider."""
    if not model:
        return "No model configured."

    if "ollama" in provider_name.lower() and api_base:
        return test_ollama(api_base)

    return test_api_provider(model, api_base)


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
    return [], "Refresh only works for Ollama providers"
