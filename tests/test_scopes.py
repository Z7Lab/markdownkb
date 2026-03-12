"""Tests for scopes endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_scopes(client):
    resp = await client.get("/api/scopes")
    assert resp.status_code == 200
    assert "scopes" in resp.json()


@pytest.mark.asyncio
async def test_create_scope_validation(client):
    # Missing required fields
    resp = await client.post("/api/scopes", json={})
    assert resp.status_code == 422
