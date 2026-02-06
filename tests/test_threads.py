"""Tests for thread CRUD endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_threads_paginated(client):
    resp = await client.get("/api/threads")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 1
    assert data["items"][0]["id"] == "abc123"


@pytest.mark.asyncio
async def test_list_threads_with_pagination_params(client):
    resp = await client.get("/api/threads?offset=0&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["offset"] == 0
    assert data["limit"] == 10


@pytest.mark.asyncio
async def test_get_thread_messages(client):
    resp = await client.get("/api/threads/abc123/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert "messages" in data
    assert len(data["messages"]) == 1
    assert data["messages"][0]["role"] == "user"


@pytest.mark.asyncio
async def test_get_thread_messages_not_found(client, app):
    app.state.chatdb.get_thread.return_value = None
    resp = await client.get("/api/threads/nonexistent/messages")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_thread(client):
    resp = await client.delete("/api/threads/abc123")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_delete_thread_not_found(client, app):
    app.state.chatdb.get_thread.return_value = None
    resp = await client.delete("/api/threads/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rename_thread(client):
    resp = await client.patch("/api/threads/abc123", json={"title": "New Title"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "renamed"


@pytest.mark.asyncio
async def test_rename_thread_not_found(client, app):
    app.state.chatdb.get_thread.return_value = None
    resp = await client.patch("/api/threads/nonexistent", json={"title": "New"})
    assert resp.status_code == 404
