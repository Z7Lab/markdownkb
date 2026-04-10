"""Command-line interface for MarkdownKB.

Wraps the REST API so you can search, chat, manage sources, and work
with buckets from the command line without the web UI or curl.

Config file: ``~/.markdownkb`` (YAML)::

    url: http://localhost:9713
    api_key: your-key-here

Or via environment variables: ``MARKDOWNKB_URL``, ``MARKDOWNKB_API_KEY``.

Usage::

    markdownkb health
    markdownkb stats
    markdownkb search "query" [--top-k N] [--json]
    markdownkb chat "message" [--json]
    markdownkb sources [list|add <path>|remove <path>]
    markdownkb index [--force]
    markdownkb buckets [list|create <name>|search <name> <query>|delete <name>]

Every command supports ``--json`` for machine-readable output and
``--url`` / ``--api-key`` to override config. Exits non-zero on error.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

CONFIG_PATH = Path.home() / ".markdownkb"
DEFAULT_URL = "http://localhost:9713"


# ── Config ─────────────────────────────────────────────────


def load_config() -> dict:
    """Load CLI config from ``~/.markdownkb`` if present."""
    if not CONFIG_PATH.exists():
        return {}
    if yaml is None:
        return {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError) as e:
        print(f"Warning: could not read {CONFIG_PATH}: {e}", file=sys.stderr)
        return {}


def resolve_url(args_url: str | None, config: dict) -> str:
    """Resolve base URL: --url > env var > config > default."""
    if args_url:
        return args_url.rstrip("/")
    env = os.environ.get("MARKDOWNKB_URL")
    if env:
        return env.rstrip("/")
    cfg = config.get("url")
    if cfg:
        return cfg.rstrip("/")
    return DEFAULT_URL


def resolve_api_key(args_key: str | None, config: dict) -> str:
    """Resolve API key: --api-key > env var > config > none."""
    if args_key:
        return args_key
    return os.environ.get("MARKDOWNKB_API_KEY") or config.get("api_key") or ""


# ── HTTP helpers ────────────────────────────────────────────


class CliError(Exception):
    """CLI failure — caught in main() and printed to stderr."""


def _headers(api_key: str) -> dict:
    h = {"Content-Type": "application/json"}
    if api_key:
        h["X-MarkdownKB-Key"] = api_key
    return h


def _request(
    method: str, url: str, api_key: str,
    body: dict | None = None, params: dict | None = None,
    timeout: float = 60.0,
) -> Any:
    """Make an HTTP request and return the parsed JSON response."""
    try:
        resp = httpx.request(
            method, url,
            headers=_headers(api_key),
            json=body,
            params=params,
            timeout=timeout,
        )
    except httpx.ConnectError as e:
        raise CliError(f"Could not reach {url} — is MarkdownKB running? ({e})") from e
    except httpx.TimeoutException as e:
        raise CliError(f"Request timed out after {timeout}s: {url}") from e
    except httpx.HTTPError as e:
        raise CliError(f"HTTP error: {e}") from e

    if resp.status_code >= 400:
        detail = resp.text
        try:
            detail = resp.json().get("detail", detail)
        except (json.JSONDecodeError, ValueError):
            pass
        raise CliError(f"{resp.status_code} {resp.reason_phrase}: {detail}")

    if not resp.content:
        return {}
    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError) as e:
        raise CliError(f"Invalid JSON response from {url}: {e}") from e


# ── Output formatting ──────────────────────────────────────


def emit(data: Any, as_json: bool, pretty_fn=None) -> None:
    """Print output — JSON if --json, otherwise the human formatter."""
    if as_json:
        print(json.dumps(data, indent=2))
        return
    if pretty_fn:
        pretty_fn(data)
    else:
        print(json.dumps(data, indent=2))


def _truncate(text: str, limit: int = 300) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


# ── Commands ────────────────────────────────────────────────


def cmd_health(base_url: str, api_key: str, as_json: bool) -> int:
    data = _request("GET", f"{base_url}/api/health", api_key)

    def pretty(d):
        print(f"  Status:          {d.get('status', '?')}")
        print(f"  Chunks indexed:  {d.get('chunks', 0)}")
        print(f"  Auth enabled:    {d.get('auth_enabled', False)}")
        print(f"  Network exposed: {d.get('network_exposed', False)}")

    emit(data, as_json, pretty)
    return 0 if data.get("status") == "ok" else 1


def cmd_stats(base_url: str, api_key: str, as_json: bool) -> int:
    data = _request("GET", f"{base_url}/api/stats", api_key)

    def pretty(d):
        print(f"  Files tracked:   {d.get('files_tracked', 0)}")
        print(f"  Files complete:  {d.get('files_complete', 0)}")
        print(f"  Files error:     {d.get('files_error', 0)}")
        print(f"  Chunks indexed:  {d.get('chunks_indexed', 0)}")
        print(f"  Embedding model: {d.get('embedding_model', '?')}")
        print(f"  Active provider: {d.get('active_provider', '?')}")
        sources = d.get("sources", [])
        if sources:
            print(f"  Sources ({len(sources)}):")
            for s in sources:
                print(f"    - {s}")

    emit(data, as_json, pretty)
    return 0


def cmd_search(base_url: str, api_key: str, query: str, top_k: int, as_json: bool) -> int:
    data = _request(
        "POST", f"{base_url}/api/search", api_key,
        body={"query": query, "top_k": top_k},
    )

    def pretty(d):
        results = d.get("results", [])
        if not results:
            print("  No results.")
            return
        for i, r in enumerate(results, 1):
            meta = r.get("metadata", {})
            score = r.get("score", 0)
            path = meta.get("source_path", "unknown")
            heading = meta.get("heading", "")
            print(f"\n  [{i}] score={score:.3f}  {path}")
            if heading:
                print(f"      # {heading}")
            doc = r.get("document", "")
            print(f"      {_truncate(doc, 240)}")
        print()

    emit(data, as_json, pretty)
    return 0


def cmd_chat(base_url: str, api_key: str, message: str, as_json: bool) -> int:
    data = _request(
        "POST", f"{base_url}/api/chat", api_key,
        body={"message": message},
        timeout=180.0,
    )

    def pretty(d):
        print(d.get("response", "").strip())
        sources = d.get("sources", [])
        if sources:
            print("\n  Sources:")
            for s in sources:
                print(f"    - {s}")

    emit(data, as_json, pretty)
    return 0


def cmd_sources_list(base_url: str, api_key: str, as_json: bool) -> int:
    data = _request("GET", f"{base_url}/api/sources", api_key)

    def pretty(d):
        sources = d.get("sources", [])
        if not sources:
            print("  No sources configured.")
            return
        for s in sources:
            print(f"  - {s}")
        inaccessible = d.get("inaccessible")
        if inaccessible:
            print("\n  ⚠ Inaccessible (not mounted in container):")
            for s in inaccessible:
                print(f"    - {s}")
            msg = d.get("message")
            if msg:
                print(f"\n  {msg}")

    emit(data, as_json, pretty)
    return 0


def cmd_sources_add(base_url: str, api_key: str, path: str, as_json: bool) -> int:
    data = _request(
        "POST", f"{base_url}/api/sources", api_key,
        body={"path": path},
    )

    def pretty(d):
        print(f"  Added: {path}")
        if d.get("docker_restart_required"):
            print(f"\n  ⚠ {d.get('message', '')}")
        sources = d.get("sources", [])
        if sources:
            print(f"\n  Now watching {len(sources)} source(s).")

    emit(data, as_json, pretty)
    return 0


def cmd_sources_remove(
    base_url: str, api_key: str, path: str, cleanup: bool, as_json: bool,
) -> int:
    data = _request(
        "DELETE", f"{base_url}/api/sources", api_key,
        body={"path": path, "cleanup": cleanup},
    )

    def pretty(d):
        print(f"  Removed: {path}")
        count = d.get("unindexed_count", 0)
        if cleanup and count:
            print(f"  Unindexed {count} file(s).")

    emit(data, as_json, pretty)
    return 0


def cmd_index(base_url: str, api_key: str, force: bool, as_json: bool) -> int:
    data = _request(
        "POST", f"{base_url}/api/index", api_key,
        body={"force": force},
    )

    def pretty(d):
        status = d.get("status", "?")
        print(f"  Status: {status}")
        msg = d.get("message")
        if msg:
            print(f"  {msg}")

    emit(data, as_json, pretty)
    return 0


def cmd_buckets_list(base_url: str, api_key: str, as_json: bool) -> int:
    data = _request("GET", f"{base_url}/api/buckets", api_key)

    def pretty(d):
        buckets = d.get("buckets", [])
        if not buckets:
            print("  No buckets.")
            return
        for b in buckets:
            expires = b.get("expires_at") or "permanent"
            name = b.get("name", "?")
            bid = b.get("id", "")[:12]
            files = b.get("file_count", 0)
            chunks = b.get("chunk_count", 0)
            print(f"  {name:30s}  id={bid}  files={files:<4}  chunks={chunks:<6}  {expires}")

    emit(data, as_json, pretty)
    return 0


def _resolve_bucket_id(base_url: str, api_key: str, name_or_id: str) -> str:
    """Resolve a bucket name to an ID, or return the ID as-is.

    Checks by exact name match first, then by ID prefix.
    """
    data = _request("GET", f"{base_url}/api/buckets", api_key)
    buckets = data.get("buckets", [])

    by_name = [b for b in buckets if b.get("name") == name_or_id]
    if len(by_name) == 1:
        return by_name[0]["id"]
    if len(by_name) > 1:
        raise CliError(f"Multiple buckets named {name_or_id!r} — use the ID instead")

    by_id = [b for b in buckets if b.get("id", "").startswith(name_or_id)]
    if len(by_id) == 1:
        return by_id[0]["id"]
    if len(by_id) > 1:
        ids = ", ".join(b["id"] for b in by_id)
        raise CliError(f"Bucket ID prefix {name_or_id!r} matches multiple: {ids}")

    raise CliError(f"No bucket named or matching ID: {name_or_id!r}")


def cmd_buckets_create(
    base_url: str, api_key: str, name: str,
    sources: list[str], expires_in: int | None, as_json: bool,
) -> int:
    body: dict = {"name": name}
    if sources:
        body["sources"] = [{"path": s, "glob": "**/*.md"} for s in sources]
    if expires_in:
        body["expires_in"] = expires_in

    data = _request(
        "POST", f"{base_url}/api/buckets", api_key,
        body=body, timeout=300.0,
    )

    def pretty(d):
        print(f"  Created bucket: {d.get('name', '?')}")
        print(f"  ID:     {d.get('id', '?')}")
        print(f"  Files:  {d.get('file_count', 0)}")
        print(f"  Chunks: {d.get('chunk_count', 0)}")

    emit(data, as_json, pretty)
    return 0


def cmd_buckets_search(
    base_url: str, api_key: str, bucket: str, query: str,
    top_k: int, as_json: bool,
) -> int:
    bucket_id = _resolve_bucket_id(base_url, api_key, bucket)
    data = _request(
        "POST", f"{base_url}/api/buckets/{bucket_id}/search", api_key,
        body={"query": query, "top_k": top_k},
    )

    def pretty(d):
        results = d.get("results", [])
        if not results:
            print("  No results.")
            return
        for i, r in enumerate(results, 1):
            score = r.get("score", 0)
            source = r.get("source", "")
            content = r.get("content", "")
            print(f"\n  [{i}] score={score:.3f}  {source}")
            print(f"      {_truncate(content, 240)}")
        print()

    emit(data, as_json, pretty)
    return 0


def cmd_buckets_delete(
    base_url: str, api_key: str, bucket: str, as_json: bool,
) -> int:
    bucket_id = _resolve_bucket_id(base_url, api_key, bucket)
    data = _request("DELETE", f"{base_url}/api/buckets/{bucket_id}", api_key)

    def pretty(d):
        print(f"  Deleted: {d.get('name', bucket)} ({bucket_id[:12]})")

    emit(data, as_json, pretty)
    return 0


# ── Argument parsing ────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="markdownkb",
        description="MarkdownKB CLI — search, chat, and manage your knowledge base.",
    )
    parser.add_argument(
        "--url",
        help="Base URL (default: env MARKDOWNKB_URL or http://localhost:9713)",
    )
    parser.add_argument(
        "--api-key",
        help="API key (default: env MARKDOWNKB_API_KEY or ~/.markdownkb)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output machine-readable JSON",
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    sub.add_parser("health", help="Check server health")
    sub.add_parser("stats", help="Show index statistics")

    sp_search = sub.add_parser("search", help="Semantic search")
    sp_search.add_argument("query", help="Search query")
    sp_search.add_argument(
        "--top-k", "-k", type=int, default=5,
        help="Number of results (default: 5)",
    )

    sp_chat = sub.add_parser("chat", help="Single-turn RAG chat")
    sp_chat.add_argument("message", help="Message to send")

    sp_index = sub.add_parser("index", help="Trigger indexing")
    sp_index.add_argument(
        "--force", action="store_true",
        help="Force full re-index (clears hashes)",
    )

    sp_sources = sub.add_parser("sources", help="Manage source directories")
    sources_sub = sp_sources.add_subparsers(dest="sources_action", metavar="<action>")
    sources_sub.add_parser("list", help="List source directories")
    sp_src_add = sources_sub.add_parser("add", help="Add a source directory")
    sp_src_add.add_argument("path", help="Absolute path to watch")
    sp_src_rm = sources_sub.add_parser("remove", help="Remove a source directory")
    sp_src_rm.add_argument("path", help="Path to remove")
    sp_src_rm.add_argument(
        "--cleanup", action="store_true",
        help="Also unindex files from this source",
    )

    sp_buckets = sub.add_parser("buckets", help="Manage temporary buckets")
    buckets_sub = sp_buckets.add_subparsers(dest="buckets_action", metavar="<action>")
    buckets_sub.add_parser("list", help="List all buckets")
    sp_b_create = buckets_sub.add_parser("create", help="Create a new bucket")
    sp_b_create.add_argument("name", help="Bucket name")
    sp_b_create.add_argument(
        "--source", action="append", default=[],
        help="Source directory path (repeatable)",
    )
    sp_b_create.add_argument(
        "--expires-in", type=int,
        help="Auto-delete after N seconds",
    )
    sp_b_search = buckets_sub.add_parser("search", help="Search within a bucket")
    sp_b_search.add_argument("bucket", help="Bucket name or ID")
    sp_b_search.add_argument("query", help="Search query")
    sp_b_search.add_argument("--top-k", "-k", type=int, default=5)
    sp_b_delete = buckets_sub.add_parser("delete", help="Delete a bucket")
    sp_b_delete.add_argument("bucket", help="Bucket name or ID")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    config = load_config()
    base_url = resolve_url(args.url, config)
    api_key = resolve_api_key(args.api_key, config)
    as_json = args.json

    try:
        if args.command == "health":
            return cmd_health(base_url, api_key, as_json)
        if args.command == "stats":
            return cmd_stats(base_url, api_key, as_json)
        if args.command == "search":
            return cmd_search(base_url, api_key, args.query, args.top_k, as_json)
        if args.command == "chat":
            return cmd_chat(base_url, api_key, args.message, as_json)
        if args.command == "index":
            return cmd_index(base_url, api_key, args.force, as_json)

        if args.command == "sources":
            action = getattr(args, "sources_action", None) or "list"
            if action == "list":
                return cmd_sources_list(base_url, api_key, as_json)
            if action == "add":
                return cmd_sources_add(base_url, api_key, args.path, as_json)
            if action == "remove":
                return cmd_sources_remove(
                    base_url, api_key, args.path, args.cleanup, as_json,
                )

        if args.command == "buckets":
            action = getattr(args, "buckets_action", None) or "list"
            if action == "list":
                return cmd_buckets_list(base_url, api_key, as_json)
            if action == "create":
                return cmd_buckets_create(
                    base_url, api_key, args.name,
                    args.source, args.expires_in, as_json,
                )
            if action == "search":
                return cmd_buckets_search(
                    base_url, api_key, args.bucket, args.query,
                    args.top_k, as_json,
                )
            if action == "delete":
                return cmd_buckets_delete(base_url, api_key, args.bucket, as_json)

        parser.print_help()
        return 1
    except CliError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
