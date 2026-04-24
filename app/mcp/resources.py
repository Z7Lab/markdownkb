"""MCP resource registration — overview, sources, scopes, buckets, file template."""

import logging
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.mcp import _state

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert a name to a URI-safe slug."""
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-") or "unnamed"


def register_resources(server: FastMCP, settings) -> None:
    """Register MCP resources: overview, source listings, scopes, buckets, file template."""
    _register_overview(server, settings)
    _register_source_listings(server, settings)
    _register_scope_listings(server, settings)
    _register_bucket_listings(server, settings)
    _register_file_template(server, settings)


def _register_overview(server: FastMCP, settings) -> None:
    @server.resource(
        "markdownkb://overview",
        name="Knowledge Base Overview",
        description="Live summary of the knowledge base: file count, chunks, sources, scopes, and buckets.",
        mime_type="text/plain",
    )
    def _overview() -> str:
        from app.storage.trackingdb import TrackingDB
        from app.storage.scopedb import ScopeDB

        cached = _state.cached_resources or {}
        tracking_owned = cached.get("tracking") is None
        scopedb_owned = True

        tracking = cached.get("tracking") or TrackingDB(settings.data_directory)
        store = cached.get("store")
        scopedb = ScopeDB(settings.data_directory)
        try:
            file_count = tracking.file_count()
            chunk_count = store.count if store else 0
            scopes = scopedb.list_scopes()
            recent = tracking.get_all_files(limit=10)
        finally:
            if tracking_owned:
                tracking.close()
            if scopedb_owned:
                scopedb.close()

        lines = ["# MarkdownKB Knowledge Base Overview", ""]
        lines.append(f"Indexed: {file_count} files, {chunk_count} chunks")
        lines.append(f"Watch directories: {len(settings.sources)}")
        lines.append(f"Named scopes: {len(scopes)}")

        if settings.plugin_enabled("buckets"):
            from app.plugins.buckets.bucketdb import BucketDB
            bucketdb = BucketDB(settings.data_directory)
            try:
                buckets = bucketdb.list_all()
            finally:
                bucketdb.close()
            lines.append(f"Buckets: {len(buckets)}")

        if settings.sources:
            lines.append("")
            lines.append("## Watch Directories")
            for src in settings.sources:
                p = Path(src)
                count = len(list(p.rglob("*.md"))) if p.is_dir() else (1 if p.is_file() else 0)
                lines.append(f"- {src} ({count} files)")

        if scopes:
            lines.append("")
            lines.append("## Named Scopes")
            for sc in scopes:
                desc = sc["name"]
                if sc.get("folders"):
                    desc += f" — {', '.join(sc['folders'])}"
                if sc.get("tags"):
                    desc += f" [tags: {', '.join(sc['tags'])}]"
                lines.append(f"- {desc}")

        if recent:
            lines.append("")
            lines.append("## Recently Indexed Files")
            for f in recent:
                name = Path(f["path"]).name
                ts = (f.get("indexed_at") or "")[:10]
                lines.append(f"- {name}" + (f" ({ts})" if ts else ""))

        return "\n".join(lines)


def _register_source_listings(server: FastMCP, settings) -> None:
    def _make_listing(source_path: str, source_name: str):
        def _listing() -> str:
            src = Path(source_path)
            if not src.exists():
                return f"Source directory not found: {source_path}"
            files = sorted(src.rglob("*.md"))
            lines = [f"# Source: {source_name}", f"Path: {source_path}", ""]
            lines += [str(f.relative_to(src)) for f in files[:500]]
            if len(files) > 500:
                lines.append(f"... and {len(files) - 500} more")
            return "\n".join(lines)
        return _listing

    for source_path in settings.sources:
        p = Path(source_path)
        uri = f"markdownkb://watch-directories/{p.name}"
        server.resource(
            uri,
            name=p.name,
            description=f"Watched directory: {source_path}",
            mime_type="text/plain",
        )(_make_listing(source_path, p.name))


def _register_scope_listings(server: FastMCP, settings) -> None:
    from app.storage.scopedb import ScopeDB

    def _make_scope_listing(scope_id: str, scope_name: str, folders: list[str], tags: list[str]):
        def _listing() -> str:
            scopedb = ScopeDB(settings.data_directory)
            try:
                scope = scopedb.get(scope_id)
            finally:
                scopedb.close()
            if scope is None:
                return f"Scope '{scope_name}' no longer exists."
            current_folders = scope["folders"]
            current_tags = scope["tags"]
            lines = [f"# Scope: {scope_name}"]
            if current_folders:
                lines.append(f"Folders: {', '.join(current_folders)}")
            if current_tags:
                lines.append(f"Tags: {', '.join(current_tags)}")
            lines.append("")
            files = []
            for folder in current_folders:
                p = Path(folder)
                if p.is_dir():
                    files.extend(sorted(p.rglob("*.md")))
            if not files:
                lines.append("(no files found in scope folders)")
            else:
                lines += [str(f) for f in files[:500]]
                if len(files) > 500:
                    lines.append(f"... and {len(files) - 500} more")
            return "\n".join(lines)
        return _listing

    try:
        _scopedb = ScopeDB(settings.data_directory)
        _scopes = _scopedb.list_scopes()
        _scopedb.close()
    except Exception:
        logger.exception("Failed to load scopes for MCP resource registration; scope resources will be unavailable")
        _scopes = []

    for scope in _scopes:
        _sid = scope["id"]
        _sname = scope["name"]
        _folders = scope.get("folders", [])
        _tags = scope.get("tags", [])
        _desc = f"Scope '{_sname}'"
        if _folders:
            _desc += f" — folders: {', '.join(_folders)}"
        if _tags:
            _desc += f" — tags: {', '.join(_tags)}"
        server.resource(
            f"markdownkb://scopes/{_slugify(_sname)}",
            name=_sname,
            description=_desc,
            mime_type="text/plain",
        )(_make_scope_listing(_sid, _sname, _folders, _tags))


def _register_bucket_listings(server: FastMCP, settings) -> None:
    if not settings.plugin_enabled("buckets"):
        return

    from app.plugins.buckets.bucketdb import BucketDB
    import json as _json

    def _make_bucket_listing(bucket_id: str, bucket_name: str):
        def _listing() -> str:
            bucketdb = BucketDB(settings.data_directory)
            try:
                bucket = bucketdb.get(bucket_id)
            finally:
                bucketdb.close()
            if bucket is None:
                return f"Bucket '{bucket_name}' no longer exists."
            sources = _json.loads(bucket.get("sources", "[]"))
            lines = [
                f"# Bucket: {bucket_name}",
                f"Files: {bucket['file_count']}  Chunks: {bucket['chunk_count']}",
                "",
            ]
            for src in sources:
                path = src.get("path", "")
                glob = src.get("glob", "**/*.md")
                lines.append(f"Source: {path}  ({glob})")
                p = Path(path)
                if p.is_dir():
                    files = sorted(p.glob(glob))
                    lines += [f"  {f}" for f in files[:200]]
                    if len(files) > 200:
                        lines.append(f"  ... and {len(files) - 200} more")
                elif p.is_file():
                    lines.append(f"  {path}")
            return "\n".join(lines)
        return _listing

    try:
        _bucketdb = BucketDB(settings.data_directory)
        _buckets = _bucketdb.list_all()
        _bucketdb.close()
    except Exception:
        logger.exception("Failed to load buckets for MCP resource registration; bucket resources will be unavailable")
        _buckets = []

    for bucket in _buckets:
        _bid = bucket["id"]
        _bname = bucket["name"]
        server.resource(
            f"markdownkb://buckets/{_slugify(_bname)}",
            name=_bname,
            description=f"Temporary bucket '{_bname}' — {bucket['file_count']} files, {bucket['chunk_count']} chunks",
            mime_type="text/plain",
        )(_make_bucket_listing(_bid, _bname))


def _register_file_template(server: FastMCP, settings) -> None:
    @server.resource(
        "markdownkb://file/{path}",
        name="File",
        description="Read the content of any indexed markdown file. Use search or list_files to find paths.",
        mime_type="text/markdown",
    )
    def _file_resource(path: str) -> str:
        resolved: str | None = None
        for src in settings.sources:
            candidate = Path(src) / path
            if candidate.exists():
                resolved = str(candidate.resolve())
                break

        if resolved is None:
            abs_candidate = Path(path)
            if abs_candidate.is_absolute() and abs_candidate.exists():
                resolved = str(abs_candidate.resolve())

        if resolved is None:
            return f"File not found: {path}"

        in_source = any(
            resolved.startswith(str(Path(s).resolve()) + "/")
            for s in settings.sources
        )
        if not in_source:
            return "Access denied: path is outside configured sources"

        try:
            return Path(resolved).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"Cannot read file: {exc}"
