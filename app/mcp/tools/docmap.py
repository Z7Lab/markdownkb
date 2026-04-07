"""MCP tool: compute document similarity map."""

from app.config import Settings
from app.storage.vectorstore import VectorStore

TOOL = {
    "name": "docmap",
    "feature_flag": None,
    "requires_plugin": "docmap",
}

_mcp = None  # Injected by register_tools()


def handler(
    min_weight: float = 0.5,
    top_k: int = 3,
    word_clouds: bool = False,
) -> dict:
    """Compute the document similarity map.

    Returns nodes (documents) and edges (similarity links) based on
    chunk-level embedding similarity between documents.

    Args:
        min_weight: Minimum edge weight threshold (default 0.5).
        top_k: Chunk pairs per document pair for scoring (default 3).
        word_clouds: Include word cloud data per cluster (default False).
    """
    from app.services.graph_service import compute_graph

    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    store: VectorStore = deps["store"]
    settings: Settings = deps["settings"]

    result = compute_graph(
        store,
        source_roots=settings.sources,
        top_k=top_k,
        word_clouds=word_clouds,
        min_weight=min_weight,
    )

    return {
        "nodes": [
            {
                "id": n["id"],
                "label": n.get("label", ""),
                "tags": n.get("tags", []),
                "cluster_id": n.get("cluster_id"),
            }
            for n in result.get("nodes", [])
        ],
        "edges": result.get("edges", []),
        "clusters": [
            {
                "id": c["id"],
                "label": c.get("label", ""),
                "doc_count": c.get("doc_count", 0),
            }
            for c in result.get("clusters", [])
        ],
        "stats": result.get("stats", {}),
    }
