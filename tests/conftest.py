"""Shared test fixtures for mdkb API tests."""

import threading
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import create_app


@dataclass
class FakeSettings:
    """Minimal settings stub for testing."""

    sources: list[str] = field(default_factory=lambda: ["/tmp/test-source"])
    global_ignore: list[str] = field(default_factory=lambda: ["**/node_modules/**", "**/.git/**"])
    api_key: str = ""
    embedding_model: str = "all-MiniLM-L6-v2"
    active_provider: str = "test"
    system_prompt: str = "You are a helpful assistant."
    default_system_prompt: str = "You are a helpful assistant."
    search_summary_prompt: str = "Provide a summary."
    default_search_summary_prompt: str = "Provide a summary."
    llm_providers: list[dict] = field(default_factory=lambda: [
        {"name": "test", "model": "test/model", "api_base": ""},
    ])
    features: dict = field(default_factory=lambda: {
        "rag_chat": True,
        "file_watcher": False,
        "rate_limiting": False,
        "mcts_planner": True,
    })
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2048
    persist_directory: str = "./data/chromadb"
    collection_name: str = "mdkb"
    data_directory: str = "./data"
    top_k: int = 5
    score_threshold: float = 0.3
    hybrid_search: bool = True
    bm25_weight: float = 0.5
    intelligent_search_enabled: bool = False
    default_top_k: int = 5
    default_score_threshold: float = 0.3
    default_hybrid_search: bool = True
    default_bm25_weight: float = 0.5
    log_level: str = "INFO"
    file_list_limit: int = 5000
    llm_num_ctx: int | None = None

    def get_active_llm_config(self):
        for p in self.llm_providers:
            if p["name"] == self.active_provider:
                return p
        return {}

    def resolve_provider_key(self, provider_name):
        import os
        env_key = os.environ.get(f"{provider_name.upper()}_API_KEY", "")
        if env_key:
            return env_key
        for p in self.llm_providers:
            if p.get("name") == provider_name:
                return p.get("api_key", "")
        return ""

    @staticmethod
    def key_is_from_env(provider_name):
        import os
        return bool(os.environ.get(f"{provider_name.upper()}_API_KEY", ""))

    def feature_enabled(self, name):
        return self.features.get(name, False)

    def add_source(self, path):
        self.sources.append(path)

    def remove_source(self, path):
        self.sources = [s for s in self.sources if s != path]

    def add_ignore_pattern(self, pattern):
        if pattern not in self.global_ignore:
            self.global_ignore.append(pattern)

    def remove_ignore_pattern(self, pattern):
        self.global_ignore = [p for p in self.global_ignore if p != pattern]

    def save(self):
        pass

    @property
    def mcp_config(self):
        return {}


@dataclass
class FakeResult:
    """Minimal search result stub."""

    document: str
    metadata: dict
    score: float


@pytest.fixture
def app():
    """Create a test app with mocked services."""
    fake_settings = FakeSettings()
    application = create_app(settings_override=fake_settings)

    application.state.settings = fake_settings

    store = MagicMock()
    store.count = 10
    store.delete_by_source = MagicMock()
    store.clear = MagicMock()
    application.state.store = store

    retriever = MagicMock()
    retriever.search.return_value = [
        FakeResult(
            document="Test document content",
            metadata={"source_path": "/tmp/test-source/doc.md"},
            score=0.9,
        )
    ]
    retriever.get_unique_folders.return_value = ["folder1", "folder2", "folder3"]
    retriever.get_unique_tags.return_value = ["tag1", "tag2"]
    application.state.retriever = retriever

    tracking = MagicMock()
    tracking.get_stats.return_value = {
        "total_files": 5,
        "complete": 4,
        "pending": 1,
        "indexing": 0,
        "error": 0,
        "total_chunks": 50,
    }
    tracking.get_all_files.return_value = [
        {
            "path": "/tmp/test-source/doc.md",
            "source_root": "/tmp/test-source",
            "status": "complete",
            "chunk_count": 3,
            "content_hash": "abc123",
            "file_size": 1024,
            "mtime": 1700000000.0,
            "include_rag": 1,
        }
    ]
    tracking.file_count.return_value = 1
    tracking.remove_files_not_in.return_value = []
    tracking.get_file.return_value = {
        "path": "/tmp/test-source/doc.md",
        "source_root": "/tmp/test-source",
        "chunk_count": 3,
        "include_rag": 1,
    }
    application.state.tracking = tracking

    chatdb = MagicMock()
    chatdb.list_threads.return_value = [
        {"id": "abc123", "title": "Test thread", "created_at": "2024-01-01", "updated_at": "2024-01-01"}
    ]
    chatdb.thread_count.return_value = 1
    chatdb.get_thread.return_value = {"id": "abc123", "title": "Test thread"}
    chatdb.get_messages.return_value = [
        {"id": 1, "thread_id": "abc123", "role": "user", "content": "Hello", "sources": None}
    ]
    chatdb.create_thread.return_value = "new123"
    application.state.chatdb = chatdb

    searchdb = MagicMock()
    searchdb.save_search.return_value = "srch001"
    searchdb.list_searches.return_value = [
        {"id": "srch001", "query": "test query", "folder": None, "tag": None, "created_at": "2024-01-01 00:00:00"}
    ]
    searchdb.search_count.return_value = 1
    searchdb.get_search.return_value = {
        "id": "srch001",
        "query": "test query",
        "folder": None,
        "tag": None,
        "summary": None,
        "result_paths": [],
        "result_count": 0,
        "result_details": [],
        "result_data": [],
        "parent_id": None,
        "created_at": "2024-01-01 00:00:00",
    }
    searchdb.mark_viewed = MagicMock()
    searchdb.get_search_versions.return_value = [
        {"id": "srch001", "query": "test query", "result_count": 0, "summary": None, "created_at": "2024-01-01 00:00:00", "parent_id": None}
    ]
    application.state.searchdb = searchdb

    scopedb = MagicMock()
    scopedb.get_scope.return_value = None
    scopedb.list_scopes.return_value = []
    application.state.scopedb = scopedb

    application.state.cancel_event = threading.Event()

    return application


@pytest.fixture
async def client(app):
    """Async HTTP test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
