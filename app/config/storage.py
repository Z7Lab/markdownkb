"""Storage configuration mixin — data dir, ChromaDB persistence, collection name."""

from pathlib import Path

from app.config._paths import default_data_dir


class StorageMixin:
    """Storage settings: data directory, ChromaDB persist dir, collection name."""

    @property
    def data_directory(self) -> str:
        """Return the data directory for all persistent state.

        Resolution order:
        1. ``storage.data_directory`` in settings.yaml (explicit override)
        2. ``MARKDOWNKB_DATA_DIR`` environment variable (Docker sets this)
        3. ``platformdirs.user_data_dir("markdownkb")`` OS-appropriate default.
        """
        raw = self._data.get("storage", {}).get("data_directory", "")
        if raw:
            return self._resolve_path(raw)
        return default_data_dir()

    @property
    def persist_directory(self) -> str:
        """Return the resolved path for ChromaDB persistence."""
        raw = self._data.get("storage", {}).get("persist_directory", "")
        if raw:
            return self._resolve_path(raw)
        return str(Path(self.data_directory) / "chromadb")

    @property
    def collection_name(self) -> str:
        """Return the ChromaDB collection name."""
        return self._data.get("storage", {}).get("collection_name", "markdownkb")
