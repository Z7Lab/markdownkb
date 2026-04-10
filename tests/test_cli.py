"""Tests for the MarkdownKB CLI (app/cli.py)."""

import io
import json
import sys
from unittest.mock import patch, MagicMock

import pytest

from app import cli


# ── Config resolution ──────────────────────────────────────


def test_resolve_url_explicit_flag():
    assert cli.resolve_url("http://foo:8080/", {}) == "http://foo:8080"


def test_resolve_url_env(monkeypatch):
    monkeypatch.setenv("MARKDOWNKB_URL", "http://env:1234/")
    assert cli.resolve_url(None, {}) == "http://env:1234"


def test_resolve_url_config(monkeypatch):
    monkeypatch.delenv("MARKDOWNKB_URL", raising=False)
    assert cli.resolve_url(None, {"url": "http://cfg:5678"}) == "http://cfg:5678"


def test_resolve_url_default(monkeypatch):
    monkeypatch.delenv("MARKDOWNKB_URL", raising=False)
    assert cli.resolve_url(None, {}) == cli.DEFAULT_URL


def test_resolve_api_key_flag_wins(monkeypatch):
    monkeypatch.setenv("MARKDOWNKB_API_KEY", "env-key")
    assert cli.resolve_api_key("flag-key", {"api_key": "cfg"}) == "flag-key"


def test_resolve_api_key_env_over_config(monkeypatch):
    monkeypatch.setenv("MARKDOWNKB_API_KEY", "env-key")
    assert cli.resolve_api_key(None, {"api_key": "cfg"}) == "env-key"


def test_resolve_api_key_config_fallback(monkeypatch):
    monkeypatch.delenv("MARKDOWNKB_API_KEY", raising=False)
    assert cli.resolve_api_key(None, {"api_key": "cfg"}) == "cfg"


def test_resolve_api_key_none(monkeypatch):
    monkeypatch.delenv("MARKDOWNKB_API_KEY", raising=False)
    assert cli.resolve_api_key(None, {}) == ""


# ── HTTP headers ────────────────────────────────────────────


def test_headers_without_key():
    h = cli._headers("")
    assert h["Content-Type"] == "application/json"
    assert "X-MarkdownKB-Key" not in h


def test_headers_with_key():
    h = cli._headers("abc")
    assert h["X-MarkdownKB-Key"] == "abc"


# ── Output formatting ──────────────────────────────────────


def test_truncate_short():
    assert cli._truncate("hello", 10) == "hello"


def test_truncate_long():
    result = cli._truncate("a" * 50, 10)
    assert result.endswith("…")
    assert len(result) <= 11


def test_emit_json(capsys):
    cli.emit({"a": 1}, as_json=True)
    out = capsys.readouterr().out
    assert json.loads(out) == {"a": 1}


def test_emit_pretty(capsys):
    def pretty(d):
        print(f"value={d['a']}")

    cli.emit({"a": 1}, as_json=False, pretty_fn=pretty)
    assert "value=1" in capsys.readouterr().out


# ── Argument parsing ───────────────────────────────────────


def test_parser_no_command():
    parser = cli.build_parser()
    args = parser.parse_args([])
    assert args.command is None


def test_parser_search():
    parser = cli.build_parser()
    args = parser.parse_args(["search", "my query", "-k", "3"])
    assert args.command == "search"
    assert args.query == "my query"
    assert args.top_k == 3


def test_parser_json_flag():
    parser = cli.build_parser()
    args = parser.parse_args(["--json", "stats"])
    assert args.json is True
    assert args.command == "stats"


def test_parser_sources_add():
    parser = cli.build_parser()
    args = parser.parse_args(["sources", "add", "/tmp/docs"])
    assert args.command == "sources"
    assert args.sources_action == "add"
    assert args.path == "/tmp/docs"


def test_parser_sources_remove_cleanup():
    parser = cli.build_parser()
    args = parser.parse_args(["sources", "remove", "/tmp/docs", "--cleanup"])
    assert args.cleanup is True


def test_parser_buckets_create_multiple_sources():
    parser = cli.build_parser()
    args = parser.parse_args([
        "buckets", "create", "test",
        "--source", "/a", "--source", "/b",
        "--expires-in", "3600",
    ])
    assert args.name == "test"
    assert args.source == ["/a", "/b"]
    assert args.expires_in == 3600


def test_parser_buckets_search():
    parser = cli.build_parser()
    args = parser.parse_args(["buckets", "search", "my-bucket", "query", "-k", "10"])
    assert args.bucket == "my-bucket"
    assert args.query == "query"
    assert args.top_k == 10


# ── Request error handling ─────────────────────────────────


def test_request_raises_on_4xx():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.reason_phrase = "Not Found"
    mock_resp.text = '{"detail": "not here"}'
    mock_resp.json.return_value = {"detail": "not here"}
    with patch("httpx.request", return_value=mock_resp):
        with pytest.raises(cli.CliError, match="404"):
            cli._request("GET", "http://x/api/foo", "")


def test_request_success_returns_json():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"ok": true}'
    mock_resp.json.return_value = {"ok": True}
    with patch("httpx.request", return_value=mock_resp):
        result = cli._request("GET", "http://x/api/foo", "")
    assert result == {"ok": True}


def test_request_connection_error():
    import httpx
    with patch("httpx.request", side_effect=httpx.ConnectError("refused")):
        with pytest.raises(cli.CliError, match="Could not reach"):
            cli._request("GET", "http://x/api/foo", "")


# ── Command output ─────────────────────────────────────────


def test_cmd_health_returns_0_on_ok(capsys):
    with patch.object(cli, "_request", return_value={"status": "ok", "chunks": 100}):
        result = cli.cmd_health("http://x", "", as_json=False)
    assert result == 0
    out = capsys.readouterr().out
    assert "ok" in out


def test_cmd_health_returns_1_on_degraded():
    with patch.object(cli, "_request", return_value={"status": "degraded"}):
        result = cli.cmd_health("http://x", "", as_json=True)
    assert result == 1


def test_cmd_buckets_list_empty(capsys):
    with patch.object(cli, "_request", return_value={"buckets": []}):
        cli.cmd_buckets_list("http://x", "", as_json=False)
    assert "No buckets" in capsys.readouterr().out


def test_resolve_bucket_id_by_name():
    with patch.object(cli, "_request", return_value={
        "buckets": [{"id": "abc123", "name": "foo"}, {"id": "def456", "name": "bar"}]
    }):
        assert cli._resolve_bucket_id("http://x", "", "foo") == "abc123"


def test_resolve_bucket_id_by_prefix():
    with patch.object(cli, "_request", return_value={
        "buckets": [{"id": "abc123def", "name": "foo"}]
    }):
        assert cli._resolve_bucket_id("http://x", "", "abc12") == "abc123def"


def test_resolve_bucket_id_not_found():
    with patch.object(cli, "_request", return_value={"buckets": []}):
        with pytest.raises(cli.CliError, match="No bucket"):
            cli._resolve_bucket_id("http://x", "", "ghost")


def test_resolve_bucket_id_ambiguous_prefix():
    with patch.object(cli, "_request", return_value={
        "buckets": [{"id": "abc1", "name": "one"}, {"id": "abc2", "name": "two"}]
    }):
        with pytest.raises(cli.CliError, match="matches multiple"):
            cli._resolve_bucket_id("http://x", "", "abc")


# ── Main dispatcher ────────────────────────────────────────


def test_main_no_args_returns_1(capsys):
    with patch.object(sys, "argv", ["markdownkb"]):
        result = cli.main()
    assert result == 1
    # Help should print to stdout
    assert "MarkdownKB CLI" in capsys.readouterr().out


def test_main_health(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["markdownkb", "health"])
    with patch.object(cli, "_request", return_value={"status": "ok", "chunks": 1}):
        result = cli.main()
    assert result == 0


def test_main_cli_error_prints_stderr(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["markdownkb", "health"])
    with patch.object(cli, "_request", side_effect=cli.CliError("boom")):
        result = cli.main()
    assert result == 1
    assert "Error: boom" in capsys.readouterr().err
