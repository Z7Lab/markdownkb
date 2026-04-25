"""Tests for file listing and management endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_files_paginated(client):
    resp = await client.get("/api/v1/files")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_files_with_pagination(client):
    resp = await client.get("/api/v1/files?offset=0&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["offset"] == 0
    assert data["limit"] == 10


@pytest.mark.asyncio
async def test_read_file_outside_sources(client):
    """Path traversal: reading files outside configured sources must be denied."""
    resp = await client.get("/api/v1/file", params={"path": "/etc/passwd"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_read_file_traversal_dotdot(client):
    """Path traversal via ../ must be denied."""
    resp = await client.get(
        "/api/v1/file",
        params={"path": "/tmp/test-source/../../etc/passwd"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_toggle_index_on(client):
    resp = await client.put(
        "/api/v1/files/include",
        json={"path": "/tmp/test-source/doc.md", "include": True},
    )
    assert resp.status_code == 200
    assert resp.json()["include_in_index"] is True


@pytest.mark.asyncio
async def test_toggle_index_off(client):
    resp = await client.put(
        "/api/v1/files/include",
        json={"path": "/tmp/test-source/doc.md", "include": False},
    )
    assert resp.status_code == 200
    assert resp.json()["include_in_index"] is False


@pytest.mark.asyncio
async def test_toggle_index_not_tracked(client, app):
    app.state.tracking.get_file.return_value = None
    resp = await client.put(
        "/api/v1/files/include",
        json={"path": "/nonexistent", "include": True},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unindex_file(client):
    resp = await client.request(
        "DELETE",
        "/api/v1/files/index",
        json={"path": "/tmp/test-source/doc.md"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "unindexed"


@pytest.mark.asyncio
async def test_unindex_file_not_tracked(client, app):
    app.state.tracking.get_file.return_value = None
    resp = await client.request(
        "DELETE",
        "/api/v1/files/index",
        json={"path": "/nonexistent"},
    )
    assert resp.status_code == 404
