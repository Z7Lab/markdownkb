"""MCP tool: get a knowledge graph entity with all its relationships."""

TOOL = {
    "name": "get_kg_entity",
    "feature_flag": None,
    "requires_plugin": "knowledge_graph",
}

_mcp = None  # Injected by register_tools()


def handler(name: str) -> dict:
    """Get detailed information about a knowledge graph entity.

    Returns the entity's type, description, source documents,
    and all incoming and outgoing typed relationships.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    kgdb = deps.get("kgdb")

    if kgdb is None:
        return {"error": "Knowledge graph not initialized (graph plugin may be disabled)"}

    entity = kgdb.get_entity(name)
    if entity is None:
        return {"error": f"Entity not found: {name}"}
    return entity
