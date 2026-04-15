"""Tests for settings and source management endpoints."""

import pytest


@pytest.mark.asyncio
async def test_get_settings(client):
    resp = await client.get("/api/v1/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_provider"] == "test"
    assert isinstance(data["providers"], list)
    assert isinstance(data["core"], dict)
    assert isinstance(data["mcp_flags"], dict)
    assert isinstance(data["plugins_enabled"], dict)
    assert isinstance(data["sources"], list)
    assert "system_prompt" in data
    assert "embedding_model" in data


@pytest.mark.asyncio
async def test_save_provider(client):
    resp = await client.put("/api/v1/settings/provider", json={
        "name": "test",
        "model": "test/new-model",
        "api_base": "",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"


@pytest.mark.asyncio
async def test_toggle_core(client):
    resp = await client.put("/api/v1/settings/core", json={
        "name": "rate_limiting",
        "enabled": True,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"


@pytest.mark.asyncio
async def test_toggle_mcp_flag(client):
    resp = await client.put("/api/v1/settings/mcp-flags", json={
        "name": "read_only",
        "enabled": True,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"


@pytest.mark.asyncio
async def test_toggle_plugin(client):
    resp = await client.put("/api/v1/settings/plugins/search/enabled", json={
        "name": "search",
        "enabled": False,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"


@pytest.mark.asyncio
async def test_update_system_prompt(client):
    resp = await client.put("/api/v1/settings/system-prompt", json={
        "prompt": "New system prompt",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"


# -- Sources --

@pytest.mark.asyncio
async def test_get_sources(client):
    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 200
    assert "/tmp/test-source" in resp.json()["sources"]


@pytest.mark.asyncio
async def test_add_source(client):
    resp = await client.post("/api/v1/sources", json={"path": "/tmp/new-source"})
    assert resp.status_code == 201
    assert "/tmp/new-source" in resp.json()["sources"]


@pytest.mark.asyncio
async def test_remove_source(client):
    resp = await client.request("DELETE", "/api/v1/sources", json={"path": "/tmp/test-source"})
    assert resp.status_code == 200
