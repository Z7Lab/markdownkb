"""Venice.ai model catalog.

Static list of available chat completion models from Venice.ai.
All use the OpenAI-compatible API with ``openai/`` LiteLLM prefix.

API Base: https://api.venice.ai/api/v1
Privacy: no data retention, privacy-preserving.
"""

# Each entry: (model_id, display_name, input_cost_per_m, output_cost_per_m, context_k)
# Sorted by tier then cost. model_id is the Venice API model name
# (without the openai/ prefix — that's added by build_model_list).

MODELS = [
    # Flagship
    ("zai-org-glm-5", "GLM 5", 1.00, 3.20, 198),
    ("kimi-k2-5", "Kimi K2.5", 0.75, 3.75, 256),
    ("kimi-k2-thinking", "Kimi K2 Thinking", 0.75, 3.20, 256),
    ("qwen3-coder-480b-a35b-instruct", "Qwen 3 Coder 480B", 0.75, 3.00, 256),
    # Strong
    ("zai-org-glm-4.7", "GLM 4.7", 0.55, 2.65, 198),
    ("qwen3-235b-a22b-thinking-2507", "Qwen 3 235B Thinking", 0.45, 3.50, 128),
    ("deepseek-v3.2", "DeepSeek V3.2", 0.40, 1.00, 160),
    ("minimax-m25", "MiniMax M2.5", 0.40, 1.60, 198),
    ("minimax-m21", "MiniMax M2.1", 0.40, 1.60, 198),
    ("qwen3-next-80b", "Qwen 3 Next 80B", 0.35, 1.90, 256),
    ("qwen3-5-35b-a3b", "Qwen 3.5 35B A3B", 0.31, 1.25, 256),
    ("qwen3-vl-235b-a22b", "Qwen 3 VL 235B", 0.25, 1.50, 256),
    # Value
    ("zai-org-glm-4.6", "GLM 4.6", 0.85, 2.75, 198),
    ("hermes-3-llama-3.1-405b", "Hermes 3 Llama 3.1 405B", 1.10, 3.00, 128),
    ("llama-3.3-70b", "Llama 3.3 70B", 0.70, 2.80, 128),
    ("qwen3-235b-a22b-instruct-2507", "Qwen 3 235B Instruct", 0.15, 0.75, 128),
    # Budget / Fast
    ("olafangensan-glm-4.7-flash-heretic", "GLM 4.7 Flash Heretic", 0.14, 0.80, 128),
    ("zai-org-glm-4.7-flash", "GLM 4.7 Flash", 0.13, 0.50, 128),
    ("llama-3.2-3b", "Llama 3.2 3B", 0.15, 0.60, 128),
    ("google-gemma-3-27b-it", "Google Gemma 3 27B", 0.12, 0.20, 198),
    ("openai-gpt-oss-120b", "OpenAI GPT OSS 120B", 0.07, 0.30, 128),
]


def get_model_ids() -> list[str]:
    """Return Venice model IDs with openai/ prefix for LiteLLM."""
    return [f"openai/{m[0]}" for m in MODELS]


def get_model_info(model_id: str) -> dict | None:
    """Return pricing and context info for a Venice model.

    Accepts both ``openai/model-name`` and bare ``model-name`` formats.
    """
    bare = model_id.split("/", 1)[-1] if "/" in model_id else model_id
    for mid, name, in_cost, out_cost, ctx_k in MODELS:
        if mid == bare:
            return {
                "display_name": name,
                "max_input_tokens": ctx_k * 1000,
                "max_output_tokens": None,
                "input_cost_per_token": in_cost / 1_000_000,
                "output_cost_per_token": out_cost / 1_000_000,
                "supports_vision": "vl" in mid.lower(),
                "supports_function_calling": False,
                "supports_response_schema": False,
                "supports_pdf_input": False,
                "litellm_provider": "venice",
                "mode": "chat",
            }
    return None
