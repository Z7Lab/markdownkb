"""Tests for health and stats endpoints."""

import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["chunks"] == 10


@pytest.mark.asyncio
async def test_stats(client):
    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["files_tracked"] == 5
    assert data["files_complete"] == 4
    assert data["chunks_indexed"] == 10
    assert data["embedding_model"] == "all-MiniLM-L6-v2"
    assert data["active_provider"] == "test"
    assert isinstance(data["sources"], list)
