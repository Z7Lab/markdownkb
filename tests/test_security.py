"""Security-focused tests: path traversal, input validation, API key auth."""

import threading
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import create_app


class TestPathTraversal:
    """Ensure the /api/file endpoint rejects paths outside configured sources."""

    @pytest.mark.asyncio
    async def test_absolute_path_outside_sources(self, client):
        resp = await client.get("/api/file", params={"path": "/etc/passwd"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_dotdot_traversal(self, client):
        resp = await client.get(
            "/api/file",
            params={"path": "/tmp/test-source/../../../etc/shadow"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_home_directory(self, client):
        resp = await client.get("/api/file", params={"path": "~/.ssh/id_rsa"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_dev_null(self, client):
        resp = await client.get("/api/file", params={"path": "/dev/null"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_proc_self(self, client):
        resp = await client.get("/api/file", params={"path": "/proc/self/environ"})
        assert resp.status_code == 403


class TestInputValidation:
    """Ensure Pydantic validation rejects malformed input."""

    @pytest.mark.asyncio
    async def test_search_empty_query(self, client):
        resp = await client.post("/api/search", json={"query": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_empty_message(self, client):
        resp = await client.post("/api/chat", json={"message": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_top_k_too_high(self, client):
        resp = await client.post("/api/search", json={"query": "test", "top_k": 999})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_top_k_zero(self, client):
        resp = await client.post("/api/search", json={"query": "test", "top_k": 0})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_pagination_negative_offset(self, client):
        resp = await client.get("/api/files?offset=-1")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_pagination_limit_too_high(self, client):
        resp = await client.get("/api/files?limit=100001")
        assert resp.status_code == 422


class TestApiKeyAuth:
    """Ensure API key middleware blocks unauthenticated requests."""

    @pytest.fixture
    def auth_app(self):
        """App with API key authentication enabled."""
        from tests.conftest import FakeSettings

        fake = FakeSettings()
        fake.api_key = "test-secret-key"
        application = create_app(settings_override=fake)
        application.state.settings = fake
        application.state.store = MagicMock(count=0)
        application.state.retriever = MagicMock()
        application.state.tracking = MagicMock()
        application.state.chatdb = MagicMock()
        application.state.searchdb = MagicMock()
        application.state.cancel_event = threading.Event()
        return application

    @pytest.fixture
    async def auth_client(self, auth_app):
        async with AsyncClient(
            transport=ASGITransport(app=auth_app),
            base_url="http://test",
        ) as c:
            yield c

    @pytest.mark.asyncio
    async def test_missing_key_returns_401(self, auth_client):
        resp = await auth_client.get("/api/health")
        # /api/health is public
        assert resp.status_code == 200

        resp = await auth_client.post("/api/search", json={"query": "test"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_key_returns_401(self, auth_client):
        resp = await auth_client.post(
            "/api/search",
            json={"query": "test"},
            headers={"X-MarkdownKB-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_correct_key_allowed(self, auth_client):
        resp = await auth_client.get(
            "/api/health",
            headers={"X-MarkdownKB-Key": "test-secret-key"},
        )
        assert resp.status_code == 200
