"""MCP tool: find the shortest path between two knowledge graph entities."""

TOOL = {
    "name": "find_relationship_path",
    "feature_flag": None,
    "requires_plugin": "knowledge_graph",
}

_mcp = None  # Injected by register_tools()


def handler(source: str, target: str, max_hops: int = 6) -> dict:
    """Find the shortest relationship path between two concepts.

    Uses BFS over typed relationships in the knowledge graph.
    Returns the path as a list of steps with entity names,
    relationship types, and direction (incoming/outgoing).
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    kgdb = deps.get("kgdb")

    if kgdb is None:
        return {"error": "Knowledge graph not initialized (graph plugin may be disabled)"}

    path = kgdb.find_path(source, target, max_hops=min(max_hops, 20))
    if path is None:
        return {
            "path": None,
            "message": f"No path found between '{source}' and '{target}' within {max_hops} hops",
        }
    return {"path": path, "hops": len(path) - 1}
