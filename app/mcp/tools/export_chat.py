"""MCP tool: export chat conversation history."""

TOOL = {
    "name": "export_chat",
    "feature_flag": None,
    "requires_plugin": "export",
}

_mcp = None  # Injected by register_tools()


def handler(format: str = "markdown") -> dict:
    """Export all chat conversations from the knowledge base.

    Args:
        format: Output format — "markdown" or "json" (default "markdown").
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    chatdb = deps.get("chatdb")

    if chatdb is None:
        return {"status": "error", "error": "Chat history not available"}

    if format not in ("markdown", "json"):
        raise ValueError("format must be 'markdown' or 'json'")

    threads = chatdb.list_threads()

    if format == "json":
        conversations = []
        for t in threads:
            messages = chatdb.get_messages(t["id"])
            conversations.append({
                "id": t["id"],
                "title": t["title"],
                "created_at": t["created_at"],
                "messages": [
                    {"role": m["role"], "content": m["content"]}
                    for m in messages
                ],
            })
        return {"conversations": conversations, "total": len(conversations)}

    # Markdown format
    parts = []
    for t in threads:
        messages = chatdb.get_messages(t["id"])
        parts.append(f"## {t['title'] or 'Untitled'}\n")
        for m in messages:
            role = "**You**" if m["role"] == "user" else "**Assistant**"
            parts.append(f"{role}: {m['content']}\n")
        parts.append("---\n")

    return {
        "content": "\n".join(parts),
        "total": len(threads),
    }
