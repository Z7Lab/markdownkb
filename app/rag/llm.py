"""LLM abstraction layer using LiteLLM with provider fallback chain."""

import logging
from typing import Generator

import litellm

from app.config import Settings

logger = logging.getLogger(__name__)


def _needs_api_key(provider: dict) -> bool:
    """Check whether a provider requires an API key to function."""
    name = provider.get("name", "").lower()
    # Ollama and other local providers don't need API keys
    if "ollama" in name or "local" in name:
        return False
    return True


def _usable_providers(settings: Settings) -> list[dict]:
    """Return providers in fallback order, skipping unconfigured ones."""
    active = settings.get_active_llm_config()
    others = [
        p for p in settings.llm_providers
        if p.get("name") != active.get("name")
    ]
    ordered = [active] + others

    usable = []
    for p in ordered:
        if not p.get("model"):
            continue
        if _needs_api_key(p) and not p.get("api_key"):
            logger.debug(
                "Skipping provider %s: no API key configured",
                p.get("name"),
            )
            continue
        usable.append(p)
    return usable


def get_completion(
    messages: list[dict],
    settings: Settings | None = None,
    stream: bool = False,
) -> str | Generator:
    """Get a completion from the active LLM provider, with fallback."""
    settings = settings or Settings.get()

    providers = _usable_providers(settings)
    if not providers:
        raise RuntimeError(
            "No usable LLM providers configured. "
            "Add an API key or configure an Ollama provider."
        )

    last_error = None
    for provider in providers:
        model = provider.get("model", "")
        api_key = provider.get("api_key", "") or None
        api_base = provider.get("api_base", "") or None

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "stream": stream,
        }
        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base

        try:
            response = litellm.completion(**kwargs)

            if stream:
                return _stream_response(response)

            return response.choices[0].message.content or ""

        except (
            litellm.APIError,
            litellm.APIConnectionError,
            litellm.AuthenticationError,
            litellm.Timeout,
            RuntimeError,
            OSError,
            ValueError,
        ) as e:
            last_error = e
            logger.warning(
                "LLM provider %s failed: %s",
                provider.get("name"), e,
            )
            continue

    raise RuntimeError(
        f"All LLM providers failed. Last error: {last_error}"
    )


def _stream_response(response) -> Generator:
    """Yield content chunks from a streaming LLM response."""
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def get_streaming_completion(
    messages: list[dict],
    settings: Settings | None = None,
) -> Generator:
    """Get a streaming completion, yielding text chunks."""
    result = get_completion(messages, settings, stream=True)
    if isinstance(result, str):
        yield result
    else:
        yield from result
