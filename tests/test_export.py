"""Tests for export endpoints."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_export_json(client):
    mock_history = MagicMock()
    mock_history.get_history.return_value = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    with patch("app.plugins.export.router.conversation_history", mock_history):
        resp = await client.post("/api/export", json={"format": "json"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "json"
    assert isinstance(data["content"], list)
    assert len(data["content"]) == 2


@pytest.mark.asyncio
async def test_export_markdown(client):
    mock_history = MagicMock()
    mock_history.get_history.return_value = [
        {"role": "user", "content": "Hello"},
    ]
    with patch("app.plugins.export.router.conversation_history", mock_history):
        resp = await client.post("/api/export", json={"format": "markdown"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "markdown"
    assert "# mdkb Conversation Export" in data["content"]
    assert "**User:**" in data["content"]
