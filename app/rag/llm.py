"""LLM abstraction layer with direct provider SDK calls and fallback chain."""

import functools
import hashlib
import logging
from typing import Generator

import anthropic
import openai

from app.config import Settings
from app.utils import parse_model as _parse_model

logger = logging.getLogger(__name__)


def _key_hash(api_key: str) -> str:
    """Return a short hash of an API key for use as a cache key."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


# Cache keyed by hash of the API key — avoids storing raw keys in memory
_anthropic_clients: dict[str, anthropic.Anthropic] = {}
_openai_clients: dict[str, openai.OpenAI] = {}


def _get_anthropic_client(api_key: str) -> anthropic.Anthropic:
    """Return a cached Anthropic client for the given API key."""
    h = _key_hash(api_key)
    if h not in _anthropic_clients:
        _anthropic_clients[h] = anthropic.Anthropic(api_key=api_key)
    return _anthropic_clients[h]


def _get_openai_client(api_key: str, api_base: str | None = None) -> openai.OpenAI:
    """Return a cached OpenAI client for the given key and base URL."""
    h = _key_hash(api_key) + (api_base or "")
    if h not in _openai_clients:
        kwargs: dict = {}
        if api_key:
            kwargs["api_key"] = api_key
        else:
            kwargs["api_key"] = "ollama"
        if api_base:
            kwargs["base_url"] = api_base
        _openai_clients[h] = openai.OpenAI(**kwargs)
    return _openai_clients[h]


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


def _extract_system_message(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Extract system message from messages list for Anthropic API.

    Returns (system_text, remaining_messages).
    """
    system_text = None
    remaining = []
    for msg in messages:
        if msg.get("role") == "system":
            system_text = msg.get("content", "")
        else:
            remaining.append(msg)
    return system_text, remaining


def _call_anthropic(
    model_name: str,
    messages: list[dict],
    api_key: str,
    temperature: float,
    max_tokens: int,
    stream: bool,
) -> object:
    """Call Anthropic Messages API."""
    client = _get_anthropic_client(api_key)
    system_text, filtered_messages = _extract_system_message(messages)

    kwargs: dict = {
        "model": model_name,
        "messages": filtered_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if system_text:
        kwargs["system"] = system_text

    if stream:
        return client.messages.create(**kwargs, stream=True)
    return client.messages.create(**kwargs)


def _call_openai(
    model_name: str,
    messages: list[dict],
    api_key: str | None,
    api_base: str | None,
    temperature: float,
    max_tokens: int,
    stream: bool,
    num_ctx: int | None = None,
) -> object:
    """Call OpenAI-compatible API (OpenAI, Ollama, Venice, etc.)."""
    client = _get_openai_client(api_key or "", api_base)

    create_kwargs: dict = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if num_ctx is not None:
        # Ollama supports num_ctx as an extra body parameter
        create_kwargs["extra_body"] = {"num_ctx": num_ctx}

    return client.chat.completions.create(**create_kwargs)


def _stream_anthropic(response) -> Generator:
    """Yield content chunks from an Anthropic streaming response."""
    with response as stream:
        for event in stream:
            if event.type == "content_block_delta" and hasattr(event.delta, "text"):
                yield event.delta.text


def _stream_openai(response) -> Generator:
    """Yield content chunks from an OpenAI streaming response."""
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


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
        api_key = (provider.get("api_key", "") or "").strip() or None
        api_base = (provider.get("api_base", "") or "").strip() or None

        provider_type, model_name = _parse_model(model)
        is_ollama = "ollama" in provider.get("name", "").lower() or provider_type == "ollama"

        # Ollama exposes an OpenAI-compatible API at /v1
        if is_ollama and api_base and not api_base.rstrip("/").endswith("/v1"):
            api_base = api_base.rstrip("/") + "/v1"

        num_ctx = settings.llm_num_ctx if is_ollama else None

        try:
            logger.info(
                "LLM request: provider=%s model=%s tokens=%d temp=%.2f",
                provider.get("name"), model, settings.llm_max_tokens, settings.llm_temperature,
            )

            if provider_type == "anthropic":
                response = _call_anthropic(
                    model_name=model_name,
                    messages=messages,
                    api_key=api_key or "",
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                    stream=stream,
                )

                if stream:
                    return _stream_anthropic(response)

                # Anthropic response: response.content[0].text
                content = response.content[0].text if response.content else None
                usage = response.usage
                if usage:
                    logger.info(
                        "LLM response: model=%s prompt_tokens=%s completion_tokens=%s",
                        model, usage.input_tokens, usage.output_tokens,
                    )
                else:
                    logger.info("LLM response: model=%s (no usage data)", model)

            else:
                # OpenAI, Ollama, and all OpenAI-compatible providers
                response = _call_openai(
                    model_name=model_name,
                    messages=messages,
                    api_key=api_key,
                    api_base=api_base,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                    stream=stream,
                    num_ctx=num_ctx,
                )

                if stream:
                    return _stream_openai(response)

                content = response.choices[0].message.content
                usage = getattr(response, "usage", None)
                if usage:
                    logger.info(
                        "LLM response: model=%s prompt_tokens=%s completion_tokens=%s",
                        model, usage.prompt_tokens, usage.completion_tokens,
                    )
                else:
                    logger.info("LLM response: model=%s (no usage data)", model)

            if content is None:
                logger.warning("LLM returned None content for model %s — trying next provider", model)
                last_error = RuntimeError(f"LLM returned None content for model {model}")
                continue
            return content

        except (
            anthropic.APIError,
            anthropic.APIConnectionError,
            anthropic.AuthenticationError,
            anthropic.APITimeoutError,
            openai.APIError,
            openai.APIConnectionError,
            openai.AuthenticationError,
            openai.APITimeoutError,
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
