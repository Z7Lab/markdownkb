"""MCP tool: multi-angle deep research synthesis."""

from app.config import Settings
from app.rag.retriever import Retriever

TOOL = {
    "name": "deep_research",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler(
    query: str,
    iterations: int = 3,
    n_approaches: int = 3,
) -> dict:
    """Run deep research on a topic using MCTS multi-angle exploration.

    Explores multiple research angles via Monte Carlo Tree Search,
    gathers evidence from the knowledge base, then synthesizes a
    comprehensive answer grounded in the best research path.

    More thorough than summarize — use this for complex topics that
    benefit from exploring multiple angles.

    Args:
        query: The research question or topic.
        iterations: MCTS depth iterations (default 3).
        n_approaches: Number of research angles to explore (default 3).
    """
    from app.planner.mcts import MCTSPlanner
    from app.rag.llm import get_completion
    from app.rag.prompts import format_context
    from app.services.deep_research import (
        DEEP_RESEARCH_SYSTEM,
        DEEP_RESEARCH_USER,
    )

    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    retriever: Retriever = deps["retriever"]
    settings: Settings = deps["settings"]

    # Run MCTS planner to explore research angles
    planner = MCTSPlanner(retriever, settings)
    result = planner.plan(query, iterations, n_approaches)

    best_plan = result.get("plan", "")

    # Gather source documents from the best path
    from app.planner.nodes import PlanNode
    all_sources: list[str] = []
    # Get chunks for context
    chunks = retriever.search(query, top_k=10)
    context = format_context(chunks)
    sources = list(dict.fromkeys(
        r.metadata.get("source_path", "") for r in chunks if r.metadata.get("source_path")
    ))

    # Synthesize using LLM
    messages = [
        {"role": "system", "content": DEEP_RESEARCH_SYSTEM},
        {"role": "user", "content": DEEP_RESEARCH_USER.format(
            query=query,
            iterations=iterations,
            n_approaches=n_approaches,
            plan=best_plan,
            context=context,
        )},
    ]

    synthesis = get_completion(messages, settings)

    return {
        "synthesis": synthesis,
        "plan": best_plan,
        "sources": sources,
        "iterations": iterations,
        "n_approaches": n_approaches,
    }
