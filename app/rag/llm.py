"""LLM abstraction layer using LiteLLM with provider fallback chain."""

import logging
from typing import Generator

import litellm

from app.config import Settings

litellm.drop_params = True

logger = logging.getLogger(__name__)


def get_completion(
    messages: list[dict],
    settings: Settings | None = None,
    stream: bool = False,
) -> str | Generator:
    """Get a completion from the active LLM provider, with fallback."""
    settings = settings or Settings.get()

    providers = settings.llm_providers
    active = settings.get_active_llm_config()

    # Build ordered list: active provider first, then fallbacks
    ordered = [active] + [
        p for p in providers
        if p.get("name") != active.get("name")
    ]

    last_error = None
    for provider in ordered:
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
