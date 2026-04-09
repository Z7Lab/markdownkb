"""Tests for settings and source management endpoints."""

import pytest


@pytest.mark.asyncio
async def test_get_settings(client):
    resp = await client.get("/api/settings")
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
    resp = await client.put("/api/settings/provider", json={
        "name": "test",
        "model": "test/new-model",
        "api_base": "",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"


@pytest.mark.asyncio
async def test_toggle_core(client):
    resp = await client.put("/api/settings/core", json={
        "name": "rate_limiting",
        "enabled": True,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"


@pytest.mark.asyncio
async def test_toggle_mcp_flag(client):
    resp = await client.put("/api/settings/mcp-flags", json={
        "name": "read_only",
        "enabled": True,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"


@pytest.mark.asyncio
async def test_toggle_plugin(client):
    resp = await client.put("/api/settings/plugins/search/enabled", json={
        "name": "search",
        "enabled": False,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"


@pytest.mark.asyncio
async def test_update_system_prompt(client):
    resp = await client.put("/api/settings/system-prompt", json={
        "prompt": "New system prompt",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"


# -- Sources --

@pytest.mark.asyncio
async def test_get_sources(client):
    resp = await client.get("/api/sources")
    assert resp.status_code == 200
    assert "/tmp/test-source" in resp.json()["sources"]


@pytest.mark.asyncio
async def test_add_source(client):
    resp = await client.post("/api/sources", json={"path": "/tmp/new-source"})
    assert resp.status_code == 200
    assert "/tmp/new-source" in resp.json()["sources"]


@pytest.mark.asyncio
async def test_remove_source(client):
    resp = await client.request("DELETE", "/api/sources", json={"path": "/tmp/test-source"})
    assert resp.status_code == 200
