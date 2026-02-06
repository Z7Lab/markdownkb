"""Tests for file listing and management endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_files_paginated(client):
    resp = await client.get("/api/files")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_files_with_pagination(client):
    resp = await client.get("/api/files?offset=0&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["offset"] == 0
    assert data["limit"] == 10


@pytest.mark.asyncio
async def test_read_file_outside_sources(client):
    """Path traversal: reading files outside configured sources must be denied."""
    resp = await client.get("/api/file", params={"path": "/etc/passwd"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_read_file_traversal_dotdot(client):
    """Path traversal via ../ must be denied."""
    resp = await client.get(
        "/api/file",
        params={"path": "/tmp/test-source/../../etc/passwd"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_exclude_file(client):
    resp = await client.post("/api/files/exclude", json={"path": "/tmp/test-source/doc.md"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "excluded"


@pytest.mark.asyncio
async def test_exclude_file_not_tracked(client, app):
    app.state.tracking.get_file.return_value = None
    resp = await client.post("/api/files/exclude", json={"path": "/nonexistent"})
    assert resp.status_code == 404
