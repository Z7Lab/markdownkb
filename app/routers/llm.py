"""LLM provider configuration and testing endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_settings
from app.ratelimit import HEAVY, LLM, STANDARD, limiter
from app.schemas import (
    LlmParamsRequest,
    ModelInfoRequest,
    ProviderSettingsRequest,
    RefreshModelsRequest,
    TestConnectionRequest,
    TestPromptRequest,
)
from app.services.llm_service import (
    build_model_list,
    get_model_capabilities,
    ping_model,
    stream_test_prompt,
    test_llm_connection,
)
from app.utils import sse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["llm"])


@router.put("/settings/provider")
@limiter.limit(STANDARD)
def save_provider(
    request: Request,
    req: ProviderSettingsRequest,
    settings: Settings = Depends(get_settings),
):
    """Save LLM provider configuration.

    API keys are never written to YAML — they must be provided via
    Docker secrets or environment variables.
    """
    settings.active_provider = req.name
    for p in settings.llm_providers:
        if p.get("name") == req.name:
            p["model"] = req.model
            p["api_base"] = req.api_base
            # Never write api_key to YAML — use secrets/env vars instead
            p.pop("api_key", None)
            break
    settings.save()
    return {"status": "saved"}


@router.put("/settings/llm-params")
@limiter.limit(STANDARD)
def save_llm_params(
    request: Request,
    req: LlmParamsRequest,
    settings: Settings = Depends(get_settings),
):
    """Save LLM generation parameters (temperature, max_tokens, num_ctx)."""
    settings.llm_temperature = req.temperature
    settings.llm_max_tokens = req.max_tokens
    settings.llm_num_ctx = req.num_ctx
    settings.save()
    return {"status": "saved"}


@router.post("/settings/test-connection")
@limiter.limit(LLM)
def test_connection(
    request: Request,
    req: TestConnectionRequest,
    settings: Settings = Depends(get_settings),
):
    """Test LLM provider connection."""
    api_key = req.api_key or settings.resolve_provider_key(req.name)
    result = test_llm_connection(
        req.name,
        req.model,
        req.api_base,
        api_key,
    )
    return {"result": result["message"], "success": result["ok"]}


@router.post("/settings/ping-model")
@limiter.limit(LLM)
def ping_model_endpoint(
    request: Request,
    req: TestConnectionRequest,
    settings: Settings = Depends(get_settings),
):
    """Ping a specific model to check availability."""
    api_key = req.api_key or settings.resolve_provider_key(req.name)
    result = ping_model(req.model, req.api_base, api_key)
    return {"result": result["message"], "success": result["ok"]}


@router.post("/settings/refresh-models")
@limiter.limit(HEAVY)
def refresh_models(request: Request, req: RefreshModelsRequest):
    """Refresh available models from provider."""
    models, status = build_model_list(
        req.name,
        req.api_base,
    )
    return {"models": models, "status": status}


@router.post("/settings/test-prompt")
@limiter.limit(LLM)
def test_prompt(
    request: Request,
    req: TestPromptRequest,
    settings: Settings = Depends(get_settings),
):
    """Test a prompt with the LLM using streaming."""
    if req.provider and req.model:
        model = req.model
        api_base = req.api_base or ""
        api_key = req.api_key or ""
    else:
        active = settings.get_active_llm_config()
        model = active.get("model", "")
        api_base = active.get("api_base", "") or ""
        api_key = active.get("api_key", "") or ""

    if not model:
        raise HTTPException(status_code=400, detail="No model configured")

    def generate():
        try:
            for event, data in stream_test_prompt(
                req.prompt,
                model,
                api_base,
                settings.llm_temperature,
                settings.llm_max_tokens,
                api_key,
                settings.llm_num_ctx,
            ):
                yield sse(event, data)
        except (RuntimeError, ConnectionError, TimeoutError) as e:
            logger.error("Test prompt error: %s", e)
            yield sse("error", {"message": "LLM request failed. Check server logs for details."})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


@router.post("/settings/model-info")
@limiter.limit(HEAVY)
def model_info(request: Request, req: ModelInfoRequest):
    """Get detailed information about a model."""
    return get_model_capabilities(req.model, req.api_base)
