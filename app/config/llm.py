"""LLM provider configuration mixin."""

import logging
import os

from app.config._paths import read_secret as _read_secret

logger = logging.getLogger(__name__)


class LLMMixin:
    """Mixin providing LLM provider, temperature, max_tokens, and key resolution."""

    @property
    def llm_providers(self) -> list[dict]:
        """Return the list of LLM provider configurations."""
        return self._data.get("llm", {}).get("providers", [])

    @property
    def active_provider(self) -> str:
        """Return the currently active LLM provider name."""
        return self._data.get("llm", {}).get(
            "active_provider", "anthropic"
        )

    @active_provider.setter
    def active_provider(self, value: str):
        """Set the active LLM provider by name."""
        self._data.setdefault("llm", {})["active_provider"] = value

    def get_active_llm_config(self) -> dict:
        """Return the config dict for the active provider.

        For ollama, the OLLAMA_API_BASE env var overrides api_base from YAML
        so Docker/remote setups work without editing settings.yaml.
        """
        config: dict = {}
        for p in self.llm_providers:
            if p.get("name") == self.active_provider:
                config = p
                break
        if not config:
            if self.llm_providers:
                logger.warning(
                    "Active provider '%s' not found in configured providers %s — "
                    "falling back to '%s'",
                    self.active_provider,
                    [p.get("name") for p in self.llm_providers],
                    self.llm_providers[0].get("name"),
                )
                config = {**self.llm_providers[0], "_fallback": True}
            else:
                logger.warning("No LLM providers configured — LLM features will be unavailable")
                return {}

        # Allow OLLAMA_API_BASE env var to override yaml for ollama provider
        if config.get("name") == "ollama" and os.environ.get("OLLAMA_API_BASE"):
            config = {**config, "api_base": os.environ["OLLAMA_API_BASE"]}

        # Resolve API key: Docker secret > env var (never from YAML)
        name = config.get("name", "")
        resolved_key = (
            _read_secret(f"{name.lower()}_api_key")
            or os.environ.get(f"{name.upper()}_API_KEY", "")
        )
        config = {**config, "api_key": resolved_key}

        return config

    def resolve_provider_key(self, provider_name: str) -> str:
        """Return the effective API key for a provider.

        Priority: Docker secret > env var.  YAML api_key fields are
        intentionally ignored — secrets should never live in config files.
        """
        return (
            _read_secret(f"{provider_name.lower()}_api_key")
            or os.environ.get(f"{provider_name.upper()}_API_KEY", "")
        )

    @staticmethod
    def key_is_from_env(provider_name: str) -> bool:
        """Return True if the provider's API key comes from a secret or env var."""
        return bool(
            _read_secret(f"{provider_name.lower()}_api_key")
            or os.environ.get(f"{provider_name.upper()}_API_KEY", "")
        )

    @property
    def llm_temperature(self) -> float:
        """Return temperature for the active provider, falling back to global default."""
        active = self.get_active_llm_config()
        if "temperature" in active:
            return active["temperature"]
        return self._data.get("llm", {}).get("temperature", 0.3)

    @llm_temperature.setter
    def llm_temperature(self, value: float):
        """Set temperature on the active provider entry."""
        with self._lock:
            for p in self.llm_providers:
                if p.get("name") == self.active_provider:
                    p["temperature"] = value
                    return
            # Fallback: active_provider name not found in providers list — write
            # to global llm.temperature so the getter's fallback chain picks it up.
            logger.warning(
                "llm_temperature setter: active provider %r not found in providers list — "
                "writing to global llm.temperature fallback",
                self.active_provider,
            )
            self._data.setdefault("llm", {})["temperature"] = value

    @property
    def llm_max_tokens(self) -> int:
        """Return max_tokens for the active provider, falling back to global default."""
        active = self.get_active_llm_config()
        if "max_tokens" in active:
            return active["max_tokens"]
        # 4096 matches the canonical default in ModelProfile.default_max_tokens
        # (app/config/profiles.py) to prevent silent truncation divergence.
        return self._data.get("llm", {}).get("max_tokens", 4096)

    @llm_max_tokens.setter
    def llm_max_tokens(self, value: int):
        """Set max_tokens on the active provider entry."""
        with self._lock:
            for p in self.llm_providers:
                if p.get("name") == self.active_provider:
                    p["max_tokens"] = value
                    return
            # Fallback: active_provider name not found in providers list — write
            # to global llm.max_tokens so the getter's fallback chain picks it up.
            logger.warning(
                "llm_max_tokens setter: active provider %r not found in providers list — "
                "writing to global llm.max_tokens fallback",
                self.active_provider,
            )
            self._data.setdefault("llm", {})["max_tokens"] = value

    @property
    def llm_num_ctx(self) -> int | None:
        """Return context window override from active provider's extra_body."""
        active = self.get_active_llm_config()
        return active.get("extra_body", {}).get("num_ctx")

    @llm_num_ctx.setter
    def llm_num_ctx(self, value: int | None):
        """Set context window on the active provider's extra_body."""
        with self._lock:
            for p in self.llm_providers:
                if p.get("name") == self.active_provider:
                    if value is None:
                        p.get("extra_body", {}).pop("num_ctx", None)
                    else:
                        p.setdefault("extra_body", {})["num_ctx"] = value
                    return
