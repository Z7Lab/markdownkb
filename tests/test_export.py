"""Tests for export endpoints."""

import pytest


@pytest.mark.asyncio
async def test_export_json(app, client):
    conv = app.state.conversation_history
    conv.add("user", "Hello")
    conv.add("assistant", "Hi there")

    resp = await client.post("/api/export", json={"format": "json"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "json"
    assert isinstance(data["content"], list)
    assert len(data["content"]) == 2


@pytest.mark.asyncio
async def test_export_markdown(app, client):
    conv = app.state.conversation_history
    conv.clear()
    conv.add("user", "Hello")

    resp = await client.post("/api/export", json={"format": "markdown"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "markdown"
    assert "# MarkdownKB Conversation Export" in data["content"]
    assert "**User:**" in data["content"]
