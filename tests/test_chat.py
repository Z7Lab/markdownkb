"""Tests for chat endpoints."""

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_chat_returns_response(client):
    def fake_respond(message, retriever, settings, **kwargs):
        if kwargs.get("sources_out") is not None:
            kwargs["sources_out"].append("/tmp/test-source/doc.md")
        yield "Test answer"

    with patch("app.routers.chat.chat_respond", side_effect=fake_respond):
        resp = await client.post("/api/v1/chat", json={
            "message": "What is this about?",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert "sources" in data


@pytest.mark.asyncio
async def test_chat_empty_message_rejected(client):
    resp = await client.post("/api/v1/chat", json={"message": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_clear_history(client):
    resp = await client.delete("/api/v1/chat/history")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cleared"


@pytest.mark.asyncio
async def test_save_plan(client):
    with patch("app.routers.chat.save_last_response_as_plan", return_value="Plan saved"):
        resp = await client.post("/api/v1/chat/save-plan", json={
            "history": [{"role": "user", "content": "test"}],
        })
    assert resp.status_code == 200
    assert resp.json()["message"] == "Plan saved"


@pytest.mark.asyncio
async def test_chat_stream_returns_sse(client):
    """Test that the streaming endpoint returns SSE events."""
    def fake_respond(message, retriever, settings, **kwargs):
        yield "Hello"
        yield "Hello world"

    with patch("app.routers.chat.chat_respond", side_effect=fake_respond):
        resp = await client.post("/api/v1/chat/stream", json={
            "message": "Hello",
        })
    assert resp.status_code == 200
    body = resp.text
    assert "event: thread" in body
    assert "event: token" in body
    assert "event: done" in body
