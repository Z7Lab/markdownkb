"""MCP tool: update tags for a document."""

TOOL = {
    "name": "update_tags",
    "feature_flag": None,
    "requires_plugin": "tags",
    "write": True,
}

_mcp = None  # Injected by register_tools()


def handler(file_path: str, tags: list[str], mode: str = "replace") -> dict:
    """Update tags for a file in the knowledge base.

    Args:
        file_path: Absolute path to the file.
        tags: List of tag strings to apply.
        mode: How to apply — "replace" (default), "add", or "remove".
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    tagdb = deps.get("tagdb")

    if tagdb is None:
        return {"status": "error", "error": "TagDB not available"}

    if mode not in ("replace", "add", "remove"):
        raise ValueError("mode must be 'replace', 'add', or 'remove'")

    if mode == "replace":
        tags_str = ", ".join(tags)
        tagdb.update_tags(file_path, tags_str)
    elif mode == "add":
        existing = tagdb.get_tags(file_path) or ""
        existing_set = {t.strip() for t in existing.split(",") if t.strip()}
        merged = sorted(existing_set | set(tags))
        tagdb.update_tags(file_path, ", ".join(merged))
    elif mode == "remove":
        existing = tagdb.get_tags(file_path) or ""
        existing_set = {t.strip() for t in existing.split(",") if t.strip()}
        remaining = sorted(existing_set - set(tags))
        tagdb.update_tags(file_path, ", ".join(remaining))

    final = tagdb.get_tags(file_path) or ""
    return {
        "status": "ok",
        "file": file_path,
        "tags": [t.strip() for t in final.split(",") if t.strip()],
    }
