"""Tests for chat endpoints."""

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_chat_returns_response(client):
    with patch("app.routers.chat.rewrite_query", return_value="test query"), \
         patch("app.routers.chat.get_completion", return_value="Test answer"):
        resp = await client.post("/api/chat", json={
            "message": "What is this about?",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert "sources" in data


@pytest.mark.asyncio
async def test_chat_empty_message_rejected(client):
    resp = await client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_clear_history(client):
    with patch("app.routers.chat.conversation_history") as mock_history:
        resp = await client.delete("/api/chat/history")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cleared"


@pytest.mark.asyncio
async def test_save_plan(client):
    with patch("app.routers.chat.save_last_response_as_plan", return_value="Plan saved"):
        resp = await client.post("/api/chat/save-plan", json={
            "history": [{"role": "user", "content": "test"}],
        })
    assert resp.status_code == 200
    assert resp.json()["message"] == "Plan saved"


@pytest.mark.asyncio
async def test_chat_stream_returns_sse(client):
    """Test that the streaming endpoint returns SSE events."""
    def fake_respond(message, retriever, settings, chatdb=None, thread_id=None, folders_filter=None, allowed_paths=None):
        yield "Hello"
        yield "Hello world"

    with patch("app.routers.chat.chat_respond", side_effect=fake_respond), \
         patch("app.routers.chat.extract_unique_sources", return_value=[]):
        resp = await client.post("/api/chat/stream", json={
            "message": "Hello",
        })
    assert resp.status_code == 200
    body = resp.text
    assert "event: thread" in body
    assert "event: token" in body
    assert "event: done" in body
