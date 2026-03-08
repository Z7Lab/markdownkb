"""Model catalog plugins.

Each subdirectory provides a static model catalog for a specific LLM
provider. A valid catalog package exposes:

    get_model_ids() -> list[str]    — model IDs with LiteLLM prefix
    get_model_info(id) -> dict|None — pricing/context/capability info

Catalogs are queried by ``llm_service.build_model_list`` when the
provider name matches the catalog directory name.
"""

import importlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CATALOGS_DIR = Path(__file__).resolve().parent


def get_catalog(provider_name: str):
    """Return the catalog module for a provider, or None."""
    name = provider_name.lower()
    for child in _CATALOGS_DIR.iterdir():
        if not child.is_dir() or child.name.startswith("_"):
            continue
        if child.name in name:
            try:
                mod = importlib.import_module(
                    f"app.plugins.catalogs.{child.name}.catalog"
                )
                return mod
            except ImportError:
                logger.debug("Failed to import catalog for %s", child.name)
    return None
