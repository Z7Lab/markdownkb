"""Ollama model catalog — dynamic.

Fetches available models from a local Ollama instance via ``/api/tags``.
Models are prefixed with ``ollama/`` for LiteLLM compatibility.

Labels show the bare model name (without the ollama/ prefix) since
Ollama model names are already user-friendly (e.g. ``qwen3:8b``).
"""

import logging
import time
from collections.abc import Iterator

import httpx

from app.security import validate_api_base

logger = logging.getLogger(__name__)

_CACHE_TTL = 30  # seconds — shorter than Venice since Ollama is local
_cache: dict = {"models": [], "api_base": "", "ts": 0.0}

# Models recommended for first-time users (small, capable, general-purpose).
STARTER_MODELS = [
    {"name": "qwen3:8b", "description": "Fast, multilingual, 8B params"},
    {"name": "llama3.1:8b", "description": "Meta's general-purpose 8B model"},
    {"name": "gemma3:4b", "description": "Google's lightweight 4B model"},
]


def _fetch_models(api_base: str) -> list[dict]:
    """Fetch and cache models from the Ollama instance.

    Returns a list of raw model dicts from ``/api/tags``.
    Results are cached in-memory for ``_CACHE_TTL`` seconds.
    """
    if not api_base:
        return []

    try:
        validate_api_base(api_base)
    except ValueError as e:
        logger.warning("Ollama api_base blocked: %s", e)
        return []

    now = time.monotonic()
    if (
        _cache["models"]
        and _cache["api_base"] == api_base
        and (now - _cache["ts"]) < _CACHE_TTL
    ):
        return _cache["models"]

    try:
        resp = httpx.get(
            f"{api_base.rstrip('/')}/api/tags", timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Failed to fetch Ollama models from %s: %s", api_base, e)
        return _cache["models"]

    models = data.get("models", [])

    _cache["models"] = models
    _cache["api_base"] = api_base
    _cache["ts"] = now
    return models


def get_model_ids(api_base: str = "") -> list[str]:
    """Return Ollama model IDs with ollama/ prefix for LiteLLM."""
    return [f"ollama/{m['name']}" for m in _fetch_models(api_base)]


def get_model_entries(api_base: str = "") -> list[dict]:
    """Return model entries with id and display label for the UI dropdown."""
    return [
        {"id": f"ollama/{m['name']}", "label": m["name"]}
        for m in _fetch_models(api_base)
    ]


def is_reachable(api_base: str) -> bool:
    """Check whether an Ollama instance is responding at *api_base*."""
    if not api_base:
        return False
    try:
        validate_api_base(api_base)
        resp = httpx.get(f"{api_base.rstrip('/')}/api/tags", timeout=3)
        return resp.status_code == 200
    except (ValueError, httpx.HTTPError):
        return False


def pull_model(model_name: str, api_base: str) -> Iterator[dict]:
    """Pull (download) a model from Ollama, yielding progress dicts.

    Each yielded dict has at minimum ``{"status": "..."}``.  During layer
    downloads Ollama also provides ``completed`` and ``total`` byte counts.
    The final dict has ``{"status": "success"}``.

    Raises ``ValueError`` on blocked URLs, ``httpx.HTTPError`` on connection /
    HTTP failures.
    """
    validate_api_base(api_base)
    bare = model_name.split("/", 1)[-1] if "/" in model_name else model_name

    with httpx.stream(
        "POST",
        f"{api_base.rstrip('/')}/api/pull",
        json={"name": bare, "stream": True},
        timeout=httpx.Timeout(connect=10, read=600, write=10, pool=10),
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                import json
                chunk = json.loads(line)
            except ValueError:
                continue
            yield chunk

    # Invalidate cache so the model list refreshes on next fetch.
    _cache["ts"] = 0.0


def get_model_info(model_id: str, api_base: str = "") -> dict | None:
    """Return model details from Ollama's ``/api/show`` endpoint.

    Accepts both ``ollama/model-name`` and bare ``model-name`` formats.
    Skips models with a non-ollama provider prefix (e.g. ``openai/``, ``venice/``)
    to prevent hitting incompatible api_base URLs with the wrong path.
    """
    if not api_base:
        return None

    # If the model has an explicit provider prefix that isn't "ollama", this
    # isn't an Ollama model — don't blindly POST to /api/show on a foreign host.
    if "/" in model_id:
        prefix = model_id.split("/", 1)[0]
        if prefix != "ollama":
            return None

    try:
        validate_api_base(api_base)
    except ValueError as e:
        logger.warning("Ollama api_base blocked in get_model_info: %s", e)
        return None

    bare = model_id.split("/", 1)[-1] if "/" in model_id else model_id

    try:
        resp = httpx.post(
            f"{api_base.rstrip('/')}/api/show",
            json={"name": bare},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.debug("Failed to fetch Ollama model info for %s: %s", bare, e)
        return None

    details = data.get("details", {})
    model_info = data.get("model_info", {})

    # Extract context length from model_info
    context_length = None
    for key, val in model_info.items():
        if key.endswith(".context_length") and isinstance(val, int):
            context_length = val
            break

    return {
        "max_input_tokens": context_length,
        "max_output_tokens": None,
        "input_cost_per_token": 0,
        "output_cost_per_token": 0,
        "supports_vision": False,
        "supports_function_calling": False,
        "supports_response_schema": False,
        "supports_pdf_input": False,
        "provider": "ollama",
        "mode": "chat",
        "ollama_details": {
            "family": details.get("family"),
            "parameter_size": details.get("parameter_size"),
            "quantization_level": details.get("quantization_level"),
            "format": details.get("format"),
        },
    }
