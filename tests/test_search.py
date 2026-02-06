"""Tests for search endpoints."""

import pytest


@pytest.mark.asyncio
async def test_search_returns_results(client):
    resp = await client.post("/api/search", json={"query": "test query"})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["document"] == "Test document content"
    assert data["results"][0]["score"] == 0.9


@pytest.mark.asyncio
async def test_search_empty_query_rejected(client):
    resp = await client.post("/api/search", json={"query": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_with_top_k(client):
    resp = await client.post("/api/search", json={"query": "test", "top_k": 3})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_top_k_out_of_range(client):
    resp = await client.post("/api/search", json={"query": "test", "top_k": 100})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_folders_paginated(client):
    resp = await client.get("/api/folders")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 3
    assert data["items"] == ["folder1", "folder2", "folder3"]


@pytest.mark.asyncio
async def test_folders_with_limit(client):
    resp = await client.get("/api/folders?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3
    assert data["offset"] == 0
    assert data["limit"] == 2


@pytest.mark.asyncio
async def test_tags_paginated(client):
    resp = await client.get("/api/tags")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] == 2
