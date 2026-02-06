"""Security-focused tests: path traversal, input validation."""

import pytest


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
        resp = await client.get("/api/files?limit=1500")
        assert resp.status_code == 422
