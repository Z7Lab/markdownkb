"""Venice.ai model catalog — dynamic.

Fetches available chat models from the Venice.ai ``/api/v1/models``
endpoint at runtime.  No API key required for the model list.

All models use the OpenAI-compatible API with ``openai/`` LiteLLM prefix.
API Base: https://api.venice.ai/api/v1
"""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

VENICE_API = "https://api.venice.ai/api/v1/models"
_CACHE_TTL = 300  # seconds — cache the model list for 5 minutes
_cache: dict = {"models": [], "ts": 0.0}


def _fetch_models() -> list[dict]:
    """Fetch and cache Venice models from the live API.

    Returns a list of raw model dicts (type=text, online only).
    Results are cached in-memory for ``_CACHE_TTL`` seconds.
    """
    now = time.monotonic()
    if _cache["models"] and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["models"]

    try:
        resp = httpx.get(VENICE_API, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Failed to fetch Venice models: %s", e)
        # Return stale cache if available, otherwise empty
        return _cache["models"]

    # Accept both {"data": [...]} envelope and bare list
    models_raw = data if isinstance(data, list) else data.get("data", [])

    # Filter: text (chat) models that are online
    models = [
        m for m in models_raw
        if m.get("type") == "text"
        and not m.get("model_spec", {}).get("offline", False)
    ]

    # Sort by input cost ascending (cheapest first)
    models.sort(
        key=lambda m: m.get("model_spec", {}).get("pricing", {}).get("input", {}).get("usd", 999)
    )

    _cache["models"] = models
    _cache["ts"] = now
    return models


def _parse_model(m: dict) -> dict:
    """Extract normalized fields from a raw Venice model dict."""
    spec = m.get("model_spec", {})
    pricing = spec.get("pricing", {})
    caps = spec.get("capabilities", {})
    return {
        "id": m["id"],
        "name": spec.get("name", m["id"]),
        "input_cost": pricing.get("input", {}).get("usd", 0),
        "output_cost": pricing.get("output", {}).get("usd", 0),
        "context_tokens": spec.get("availableContextTokens", 0),
        "max_output_tokens": spec.get("maxCompletionTokens", 0),
        "function_calling": caps.get("supportsFunctionCalling", False),
        "vision": caps.get("supportsVision", False),
        "response_schema": caps.get("supportsResponseSchema", False),
        "privacy": spec.get("privacy", "unknown"),
    }


def get_model_ids() -> list[str]:
    """Return Venice model IDs with openai/ prefix for LiteLLM."""
    return [f"openai/{m['id']}" for m in _fetch_models()]


def get_model_entries() -> list[dict]:
    """Return model entries with id and display label for the UI dropdown."""
    entries = []
    for raw in _fetch_models():
        p = _parse_model(raw)
        ctx_k = p["context_tokens"] // 1000
        out_k = p["max_output_tokens"] // 1000
        privacy_icon = "\U0001f512" if p["privacy"] == "private" else "\U0001f464"
        label = (
            f"{p['name']}  —  {ctx_k}K ctx, {out_k}K out, "
            f"${p['input_cost']:.2f}/${p['output_cost']:.2f}/M  {privacy_icon} {p['privacy']}"
        )
        entries.append({"id": f"openai/{p['id']}", "label": label})
    return entries


def get_model_info(model_id: str) -> dict | None:
    """Return pricing and capability info for a Venice model.

    Accepts both ``openai/model-name`` and bare ``model-name`` formats.
    """
    bare = model_id.split("/", 1)[-1] if "/" in model_id else model_id
    for raw in _fetch_models():
        if raw["id"] == bare:
            p = _parse_model(raw)
            return {
                "display_name": p["name"],
                "max_input_tokens": p["context_tokens"],
                "max_output_tokens": p["max_output_tokens"],
                "input_cost_per_token": p["input_cost"] / 1_000_000,
                "output_cost_per_token": p["output_cost"] / 1_000_000,
                "supports_vision": p["vision"],
                "supports_function_calling": p["function_calling"],
                "supports_response_schema": p["response_schema"],
                "supports_pdf_input": False,
                "privacy": p["privacy"],
                "provider": "venice",
                "mode": "chat",
            }
    return None
