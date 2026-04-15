"""LLM provider configuration and testing endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.deps import get_settings
from app.ratelimit import HEAVY, LLM, STANDARD, limiter
from app.plugins.catalogs.ollama.catalog import (
    STARTER_MODELS as OLLAMA_STARTER_MODELS,
    is_reachable as ollama_is_reachable,
    pull_model as ollama_pull_model,
)
from app.schemas import (
    LlmParamsRequest,
    ModelInfoRequest,
    OllamaPullRequest,
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

router = APIRouter(prefix="/api/v1", tags=["llm"])


@router.put("/settings/provider")
@limiter.limit(STANDARD)
def save_provider(
    request: Request,
    req: ProviderSettingsRequest,
    settings: Settings = Depends(get_settings),
):
    """Save LLM provider configuration.

    API keys are written to the data secrets directory (not YAML).
    """
    settings.active_provider = req.name
    found = False
    for p in settings.llm_providers:
        if p.get("name") == req.name:
            p["model"] = req.model
            p["api_base"] = req.api_base
            p.pop("api_key", None)  # never in YAML
            found = True
            break
    if not found:
        # New provider — add it to the list
        settings.llm_providers.append({
            "name": req.name,
            "model": req.model,
            "api_base": req.api_base,
        })
    settings.save()

    # Write API key to secrets directory if provided
    if req.api_key:
        from app.config import _data_secrets_dir
        secret_name = f"{req.name.lower()}_api_key"
        target = _data_secrets_dir() / secret_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(req.api_key.strip())
        logger.info("Saved API key for provider '%s' to %s", req.name, target)

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
    # Fill missing fields from provider config
    model = req.model
    api_base = req.api_base
    if not model or not api_base:
        provider_cfg = next(
            (p for p in settings.llm_providers if p.get("name") == req.name),
            {},
        )
        model = model or provider_cfg.get("model", "")
        api_base = api_base or provider_cfg.get("api_base", "")
    api_key = req.api_key or settings.resolve_provider_key(req.name)
    result = test_llm_connection(req.name, model, api_base, api_key)
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
    active = settings.get_active_llm_config()
    if req.provider and req.model:
        model = req.model
        api_base = req.api_base or ""
        api_key = req.api_key or ""
        extra_body = None
    else:
        model = active.get("model", "")
        api_base = active.get("api_base", "") or ""
        api_key = active.get("api_key", "") or ""
        extra_body = active.get("extra_body")

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
                extra_body,
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


# -- Ollama management --


@router.get("/settings/ollama/status")
@limiter.limit(STANDARD)
def ollama_status(request: Request, settings: Settings = Depends(get_settings)):
    """Check Ollama reachability and return starter model suggestions."""
    # Find the Ollama provider config for its api_base.
    api_base = ""
    for p in settings.llm_providers:
        if "ollama" in p.get("name", "").lower():
            api_base = p.get("api_base", "")
            break
    reachable = ollama_is_reachable(api_base) if api_base else False
    return {
        "reachable": reachable,
        "api_base": api_base,
        "starter_models": OLLAMA_STARTER_MODELS,
    }


@router.post("/settings/ollama/pull")
@limiter.limit(HEAVY)
def pull_ollama_model(
    request: Request,
    req: OllamaPullRequest,
    settings: Settings = Depends(get_settings),
):
    """Pull (download) a model from Ollama, streaming progress via SSE."""
    # Resolve api_base from request or from the Ollama provider config.
    api_base = req.api_base
    if not api_base:
        for p in settings.llm_providers:
            if "ollama" in p.get("name", "").lower():
                api_base = p.get("api_base", "")
                break
    if not api_base:
        raise HTTPException(400, "No Ollama API base configured")

    import httpx as _httpx

    def generate():
        try:
            for chunk in ollama_pull_model(req.model_name, api_base):
                status = chunk.get("status", "")
                completed = chunk.get("completed", 0)
                total = chunk.get("total", 0)
                percent = (completed / total * 100) if total else 0.0
                yield sse("progress", {
                    "status": status,
                    "completed": completed,
                    "total": total,
                    "percent": round(percent, 1),
                })
                if status == "success":
                    yield sse("done", {"status": "success", "model": req.model_name})
        except _httpx.HTTPError as e:
            logger.error("Ollama pull failed for %s: %s", req.model_name, e)
            yield sse("error", {"message": f"Pull failed: {e}"})
        except (RuntimeError, OSError) as e:
            logger.error("Ollama pull error for %s: %s", req.model_name, e)
            yield sse("error", {"message": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream")
