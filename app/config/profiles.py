"""Model profiles — per-family behavioral config, matched by glob pattern.

Built-in profiles cover common model families. Users can override or add
profiles via YAML files in config/models/*.yaml.

Matching uses the model name after stripping the provider prefix
(e.g. "ollama/qwen3:8b" → "qwen3:8b") and applies fnmatch glob patterns.
The first matching profile wins; built-ins are checked last.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

THINKING_FORMATS = frozenset({"reasoning_content", "xml_tags", "none"})
CONTEXT_MANAGED_BY = frozenset({"server", "api", "provider"})


@dataclass
class ModelProfile:
    pattern: str
    thinking_format: str = "none"        # reasoning_content | xml_tags | none
    default_max_tokens: int = 4096
    default_temperature: float = 0.3
    context_managed_by: str = "server"   # server | api | provider
    max_context: int | None = None
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "pattern": self.pattern,
            "thinking_format": self.thinking_format,
            "default_max_tokens": self.default_max_tokens,
            "default_temperature": self.default_temperature,
            "context_managed_by": self.context_managed_by,
            "max_context": self.max_context,
            "notes": self.notes,
        }


# ── Built-in profiles ──────────────────────────────────────────────────────
# Ordered: more specific patterns first.

_BUILT_INS: list[ModelProfile] = [
    # DeepSeek R-series — reasoning via separate reasoning_content field
    ModelProfile(
        pattern="deepseek-r*",
        thinking_format="reasoning_content",
        default_max_tokens=8192,
        default_temperature=0.6,
        context_managed_by="api",
        max_context=131072,
        notes="DeepSeek R1/R2: thinking arrives in reasoning_content, not content.",
    ),
    # DeepSeek base (non-reasoning)
    ModelProfile(
        pattern="deepseek*",
        thinking_format="none",
        default_max_tokens=8192,
        default_temperature=0.3,
        context_managed_by="api",
        max_context=131072,
    ),
    # Gemma 4 — reasoning_content field, low max_tokens starves content
    ModelProfile(
        pattern="gemma-4*",
        thinking_format="reasoning_content",
        default_max_tokens=8192,
        default_temperature=0.3,
        context_managed_by="server",
        max_context=131072,
        notes="Gemma 4: thinking in reasoning_content. Keep max_tokens high or content will be empty.",
    ),
    # Gemma (non-4)
    ModelProfile(
        pattern="gemma*",
        thinking_format="none",
        default_max_tokens=4096,
        default_temperature=0.3,
        context_managed_by="server",
        max_context=8192,
    ),
    # QwQ — dedicated reasoning model, xml_tags
    ModelProfile(
        pattern="qwq*",
        thinking_format="xml_tags",
        default_max_tokens=8192,
        default_temperature=0.6,
        context_managed_by="server",
        max_context=131072,
        notes="QwQ: reasoning wrapped in <think> XML tags.",
    ),
    # Qwen3 — thinking via <think> tags when in thinking mode
    ModelProfile(
        pattern="qwen3*",
        thinking_format="xml_tags",
        default_max_tokens=8192,
        default_temperature=0.6,
        context_managed_by="server",
        max_context=32768,
        notes="Qwen3: thinking via <think> XML tags. Non-thinking mode tags are stripped harmlessly.",
    ),
    # Qwen (older)
    ModelProfile(
        pattern="qwen*",
        thinking_format="none",
        default_max_tokens=4096,
        default_temperature=0.3,
        context_managed_by="server",
        max_context=32768,
    ),
    # Llama
    ModelProfile(
        pattern="llama*",
        thinking_format="none",
        default_max_tokens=4096,
        default_temperature=0.3,
        context_managed_by="server",
        max_context=8192,
    ),
    # Mistral / Mistral-derived
    ModelProfile(
        pattern="mistral*",
        thinking_format="none",
        default_max_tokens=4096,
        default_temperature=0.3,
        context_managed_by="server",
        max_context=32768,
    ),
    # Claude — Anthropic SDK handles thinking natively; strip_thinking not needed
    ModelProfile(
        pattern="claude*",
        thinking_format="none",
        default_max_tokens=4096,
        default_temperature=0.3,
        context_managed_by="provider",
        notes="Claude: thinking handled by Anthropic SDK. Context managed by provider.",
    ),
    # GPT and o-series
    ModelProfile(
        pattern="gpt*",
        thinking_format="none",
        default_max_tokens=4096,
        default_temperature=0.3,
        context_managed_by="provider",
    ),
    ModelProfile(
        pattern="o1*",
        thinking_format="none",
        default_max_tokens=8192,
        default_temperature=1.0,
        context_managed_by="provider",
        notes="o1/o3: reasoning managed by OpenAI; temperature must be 1.",
    ),
    ModelProfile(
        pattern="o3*",
        thinking_format="none",
        default_max_tokens=8192,
        default_temperature=1.0,
        context_managed_by="provider",
    ),
    # Phi (Microsoft)
    ModelProfile(
        pattern="phi*",
        thinking_format="none",
        default_max_tokens=4096,
        default_temperature=0.3,
        context_managed_by="server",
        max_context=16384,
    ),
]

_DEFAULT_PROFILE = ModelProfile(
    pattern="*",
    thinking_format="none",
    default_max_tokens=4096,
    default_temperature=0.3,
    context_managed_by="server",
)


# ── User profile loader ────────────────────────────────────────────────────

def _load_user_profiles(config_dir: Path) -> list[ModelProfile]:
    models_dir = config_dir / "models"
    if not models_dir.is_dir():
        return []
    profiles = []
    for path in sorted(models_dir.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text())
            if not isinstance(raw, dict) or "pattern" not in raw:
                logger.warning("profiles: skipping %s — missing 'pattern' key", path.name)
                continue
            tf = raw.get("thinking_format", "none")
            if tf not in THINKING_FORMATS:
                logger.warning("profiles: %s has unknown thinking_format %r, using 'none'", path.name, tf)
                tf = "none"
            cm = raw.get("context_managed_by", "server")
            if cm not in CONTEXT_MANAGED_BY:
                cm = "server"
            profiles.append(ModelProfile(
                pattern=raw["pattern"],
                thinking_format=tf,
                default_max_tokens=int(raw.get("default_max_tokens", 4096)),
                default_temperature=float(raw.get("default_temperature", 0.3)),
                context_managed_by=cm,
                max_context=raw.get("max_context"),
                notes=raw.get("notes", ""),
            ))
        except Exception as exc:
            logger.warning("profiles: failed to load %s: %s", path, exc)
    return profiles


# ── Public API ─────────────────────────────────────────────────────────────

def _strip_prefix(model_id: str) -> str:
    """Return model name without provider prefix (e.g. 'ollama/qwen3:8b' → 'qwen3:8b')."""
    return model_id.split("/", 1)[-1] if "/" in model_id else model_id


def get_profile(model_id: str, config_dir: Path | None = None) -> ModelProfile:
    """Return the best-matching profile for a model ID.

    User profiles (from config/models/*.yaml) take priority over built-ins.
    Falls back to _DEFAULT_PROFILE if nothing matches.
    """
    name = _strip_prefix(model_id).lower()

    # User profiles checked first
    if config_dir is not None:
        for p in _load_user_profiles(config_dir):
            if fnmatch(name, p.pattern.lower()):
                return p

    for p in _BUILT_INS:
        if fnmatch(name, p.pattern.lower()):
            return p

    return _DEFAULT_PROFILE
