"""Settings and source management endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_settings
from app.ratelimit import HEAVY, LLM, STANDARD, limiter
from app.schemas import (
    AddSourceRequest,
    FeatureToggleRequest,
    ModelInfoRequest,
    ProviderSettingsRequest,
    RefreshModelsRequest,
    RemoveSourceRequest,
    SystemPromptRequest,
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

router = APIRouter(prefix="/api", tags=["settings"])


# -- Sources --

@router.get("/sources")
@limiter.limit(STANDARD)
def get_sources(request: Request, settings: Settings = Depends(get_settings)):
    return {"sources": settings.sources}


@router.post("/sources")
@limiter.limit(STANDARD)
def add_source(
    request: Request,
    req: AddSourceRequest,
    settings: Settings = Depends(get_settings),
):
    settings.add_source(req.path)
    settings.save()
    return {"sources": settings.sources}


@router.delete("/sources")
@limiter.limit(STANDARD)
def remove_source(
    request: Request,
    req: RemoveSourceRequest,
    settings: Settings = Depends(get_settings),
):
    settings.remove_source(req.path)
    settings.save()
    return {"sources": settings.sources}


# -- Settings --

@router.get("/settings")
@limiter.limit(STANDARD)
def get_settings_endpoint(request: Request, settings: Settings = Depends(get_settings)):
    active_cfg = settings.get_active_llm_config()
    return {
        "active_provider": settings.active_provider,
        "providers": [
            {
                "name": p["name"],
                "model": p.get("model", ""),
                "api_base": p.get("api_base", ""),
            }
            for p in settings.llm_providers
        ],
        "features": settings.features,
        "sources": settings.sources,
        "active_model": active_cfg.get("model", ""),
        "active_api_base": active_cfg.get("api_base", ""),
        "system_prompt": settings.system_prompt,
        "default_system_prompt": settings.default_system_prompt,
        "embedding_model": settings.embedding_model,
    }


@router.put("/settings/provider")
@limiter.limit(STANDARD)
def save_provider(
    request: Request,
    req: ProviderSettingsRequest,
    settings: Settings = Depends(get_settings),
):
    settings.active_provider = req.name
    for p in settings.llm_providers:
        if p.get("name") == req.name:
            p["model"] = req.model
            p["api_base"] = req.api_base
            break
    settings.save()
    return {"status": "saved"}


@router.post("/settings/test-connection")
@limiter.limit(LLM)
def test_connection(request: Request, req: TestConnectionRequest):
    result = test_llm_connection(
        req.name,
        req.model,
        req.api_base,
    )
    return {"result": result}


@router.post("/settings/ping-model")
@limiter.limit(LLM)
def ping_model_endpoint(request: Request, req: TestConnectionRequest):
    result = ping_model(req.model, req.api_base)
    return {"result": result}


@router.post("/settings/refresh-models")
@limiter.limit(HEAVY)
def refresh_models(request: Request, req: RefreshModelsRequest):
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
    if req.provider and req.model:
        model = req.model
        api_base = req.api_base or ""
    else:
        active = settings.get_active_llm_config()
        model = active.get("model", "")
        api_base = active.get("api_base", "") or ""

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
            ):
                yield sse(event, data)
        except (RuntimeError, ConnectionError, TimeoutError) as e:
            yield sse("error", {"message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


@router.post("/settings/model-info")
@limiter.limit(HEAVY)
def model_info(request: Request, req: ModelInfoRequest):
    return get_model_capabilities(req.model, req.api_base)


@router.put("/settings/features")
@limiter.limit(STANDARD)
def toggle_feature(
    request: Request,
    req: FeatureToggleRequest,
    settings: Settings = Depends(get_settings),
):
    settings.features[req.name] = req.enabled
    settings.save()
    return {"status": "saved"}


@router.put("/settings/system-prompt")
@limiter.limit(STANDARD)
def update_system_prompt(
    request: Request,
    req: SystemPromptRequest,
    settings: Settings = Depends(get_settings),
):
    settings.system_prompt = req.prompt
    settings.save()
    return {"status": "saved"}
