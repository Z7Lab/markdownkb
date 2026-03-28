"""Tests for retrieval preset endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_presets_empty(client):
    resp = await client.get("/api/settings/presets")
    assert resp.status_code == 200
    assert resp.json()["presets"] == []


@pytest.mark.asyncio
async def test_create_preset(client, app):
    resp = await client.post("/api/settings/presets", json={
        "name": "Detailed",
        "settings": {"top_k": 10, "score_threshold": 0.25, "hybrid_search": True, "bm25_weight": 0.5},
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"
    assert resp.json()["id"] == "preset001"
    app.state.presetsdb.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_preset_snapshot_current(client, app):
    """Creating without settings snapshots current retrieval config."""
    resp = await client.post("/api/settings/presets", json={"name": "Current"})
    assert resp.status_code == 200
    call_args = app.state.presetsdb.create.call_args
    settings = call_args[0][1]
    assert "top_k" in settings
    assert "score_threshold" in settings


@pytest.mark.asyncio
async def test_create_preset_no_name(client):
    resp = await client.post("/api/settings/presets", json={"name": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_preset(client):
    resp = await client.put("/api/settings/presets/preset001", json={
        "name": "Renamed",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "updated"


@pytest.mark.asyncio
async def test_update_preset_not_found(client, app):
    app.state.presetsdb.update.return_value = False
    resp = await client.put("/api/settings/presets/nonexistent", json={
        "name": "Nope",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_preset(client):
    resp = await client.delete("/api/settings/presets/preset001")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_delete_preset_not_found(client, app):
    app.state.presetsdb.delete.return_value = False
    resp = await client.delete("/api/settings/presets/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_load_preset(client, app):
    app.state.presetsdb.get.return_value = {
        "id": "preset001",
        "name": "Detailed",
        "settings": {"top_k": 10, "score_threshold": 0.2, "hybrid_search": True, "bm25_weight": 0.5},
    }
    resp = await client.post("/api/settings/presets/preset001/load")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "loaded"
    assert data["name"] == "Detailed"
    # Verify settings were applied
    assert app.state.settings.top_k == 10
    assert app.state.settings.score_threshold == 0.2


@pytest.mark.asyncio
async def test_load_preset_not_found(client, app):
    app.state.presetsdb.get.return_value = None
    resp = await client.post("/api/settings/presets/nonexistent/load")
    assert resp.status_code == 404
