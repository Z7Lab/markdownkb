import logging
from typing import Generator

from app.config import Settings

logger = logging.getLogger(__name__)


def _get_litellm():
    import litellm
    litellm.drop_params = True
    return litellm


def get_completion(messages: list[dict], settings: Settings | None = None,
                   stream: bool = False) -> str | Generator:
    settings = settings or Settings.get()
    litellm = _get_litellm()

    providers = settings.llm_providers
    active = settings.get_active_llm_config()

    # Build ordered list: active provider first, then fallbacks
    ordered = [active] + [p for p in providers if p.get("name") != active.get("name")]

    last_error = None
    for provider in ordered:
        model = provider.get("model", "")
        api_key = provider.get("api_key", "") or None
        api_base = provider.get("api_base", "") or None

        # Pick up env vars for keys
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

        except Exception as e:
            last_error = e
            logger.warning(f"LLM provider {provider.get('name')} failed: {e}")
            continue

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


def _stream_response(response) -> Generator:
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def get_streaming_completion(messages: list[dict],
                             settings: Settings | None = None) -> Generator:
    result = get_completion(messages, settings, stream=True)
    if isinstance(result, str):
        yield result
    else:
        yield from result
