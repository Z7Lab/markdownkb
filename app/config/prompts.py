"""Prompt template configuration mixin."""

import logging

logger = logging.getLogger(__name__)


class PromptsMixin:
    """Mixin providing prompt template loading, caching, and override management."""

    def get_prompt(self, name: str) -> str:
        """Load a prompt template from config/prompts/{name}.md.

        Results are cached per name until reload_prompts() is called.
        Raises FileNotFoundError if the prompt file is missing.
        """
        with self._lock:
            if name in self._prompt_cache:
                return self._prompt_cache[name]

            prompt_file = self._path.parent / "prompts" / f"{name}.md"
            text = prompt_file.read_text(encoding="utf-8").strip()
            logger.debug("Loaded prompt '%s' from %s", name, prompt_file)
            self._prompt_cache[name] = text
            return text

    def reload_prompts(self):
        """Clear the prompt cache so files are re-read on next access."""
        self._prompt_cache.clear()

    @property
    def system_prompt(self) -> str:
        """Return the RAG system prompt (settings.yaml override > file)."""
        override = self._data.get("prompts", {}).get("system_prompt")
        if override:
            return override
        return self.get_prompt("system")

    @system_prompt.setter
    def system_prompt(self, value: str):
        """Set the RAG system prompt (written to settings.yaml)."""
        with self._lock:
            self._data.setdefault("prompts", {})["system_prompt"] = value

    @property
    def default_system_prompt(self) -> str:
        """Return the file-based default system prompt."""
        return self.get_prompt("system")

    @property
    def search_summary_prompt(self) -> str:
        """Return the search summary prompt (settings.yaml override > file)."""
        override = self._data.get("prompts", {}).get("search_summary_prompt")
        if override:
            return override
        return self.get_prompt("search_summary_system")

    @search_summary_prompt.setter
    def search_summary_prompt(self, value: str):
        """Set the search summary prompt (written to settings.yaml)."""
        with self._lock:
            self._data.setdefault("prompts", {})["search_summary_prompt"] = value

    @property
    def default_search_summary_prompt(self) -> str:
        """Return the file-based default search summary prompt."""
        return self.get_prompt("search_summary_system")
