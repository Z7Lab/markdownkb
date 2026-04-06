"""MCP tool: query the knowledge graph for entities and relationships."""

TOOL = {
    "name": "query_knowledge_graph",
    "feature_flag": None,
    "requires_plugin": "knowledge_graph",
}

_mcp = None  # Injected by register_tools()


def handler(
    entity_types: str = "",
    relationship_types: str = "",
    limit: int = 100,
) -> dict:
    """Query the knowledge graph for entities and their typed relationships.

    Filter by entity types (concept, technology, tool, process, etc.)
    or relationship types (uses, is-a, part-of, relates-to, etc.).
    Returns entities with mention counts and relationships with provenance.
    """
    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    kgdb = deps.get("kgdb")

    if kgdb is None:
        return {"error": "Knowledge graph not initialized (graph plugin may be disabled)"}

    et = [t.strip() for t in entity_types.split(",") if t.strip()] or None
    rt = [t.strip() for t in relationship_types.split(",") if t.strip()] or None

    entities = kgdb.get_all_entities(entity_types=et)[:limit]
    relationships = kgdb.get_all_relationships(rel_types=rt)[:limit * 3]

    return {
        "entities": entities,
        "relationships": relationships,
        "entity_types": kgdb.get_entity_types(),
        "relationship_types": kgdb.get_relationship_types(),
        "stats": kgdb.get_stats(),
    }
