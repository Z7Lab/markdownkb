"""Tests for the X-Request-ID middleware and log-record factory."""

import pytest

from app.logging_ctx import install_request_id_log_factory, request_id_var


def test_log_factory_adds_request_id_attribute():
    install_request_id_log_factory()
    import logging
    factory = logging.getLogRecordFactory()
    rec = factory(
        "x", logging.INFO, "", 0, "hello", None, None,
    )
    # Default value when no request is in scope.
    assert getattr(rec, "request_id", None) == "-"


def test_factory_picks_up_contextvar():
    install_request_id_log_factory()
    import logging
    factory = logging.getLogRecordFactory()
    tok = request_id_var.set("abc123")
    try:
        rec = factory(
            "x", logging.INFO, "", 0, "hi", None, None,
        )
        assert rec.request_id == "abc123"
    finally:
        request_id_var.reset(tok)


@pytest.mark.asyncio
async def test_request_id_header_generated_and_echoed(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    rid = r.headers.get("X-Request-ID", "")
    assert rid and rid != "-"


@pytest.mark.asyncio
async def test_request_id_header_propagated(client):
    r = await client.get("/api/v1/health", headers={"X-Request-ID": "my-rid-42"})
    assert r.headers.get("X-Request-ID") == "my-rid-42"


@pytest.mark.asyncio
async def test_request_id_length_capped(client):
    # 200-char id from a misbehaving client must be truncated.
    long_id = "A" * 200
    r = await client.get("/api/v1/health", headers={"X-Request-ID": long_id})
    assert len(r.headers.get("X-Request-ID", "")) <= 64
