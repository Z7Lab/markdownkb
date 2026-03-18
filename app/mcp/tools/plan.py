"""MCP tool: generate an implementation plan using MCTS."""

from app.config import Settings
from app.rag.retriever import Retriever

TOOL = {
    "name": "plan",
    "feature_flag": None,
}

_mcp = None  # Injected by register_tools()


def handler(
    request: str,
    iterations: int = 3,
    n_approaches: int = 3,
    save: bool = True,
) -> dict:
    """Generate an implementation plan grounded in the knowledge base.

    Uses Monte Carlo Tree Search (MCTS) to explore multiple approaches,
    score them against the knowledge base, and synthesize the best plan.

    Args:
        request: What you want planned — be specific about goals and constraints.
        iterations: MCTS depth iterations (default 3). Higher = deeper analysis.
        n_approaches: Number of initial approaches to generate (default 3).
        save: Whether to save the plan to the plan database (default True).
    """
    from app.services.planner_service import run_planner

    ctx = _mcp.get_context()
    deps = ctx.request_context.lifespan_context
    retriever: Retriever = deps["retriever"]
    settings: Settings = deps["settings"]

    result = run_planner(
        request,
        retriever,
        settings,
        iterations=iterations,
        n_approaches=n_approaches,
    )

    # Save to PlanDB if requested and available
    plandb = deps.get("plandb")
    if save and plandb:
        title = f"[agent] {request[:50].strip()}"
        if len(request) > 50:
            title += "..."
        plan_id = plandb.save(title, result.get("plan", ""), query=request)
        result["plan_id"] = plan_id

    return {
        "plan": result.get("plan", ""),
        "approaches": [
            {"content": a.get("content", ""), "score": a.get("score", 0)}
            for a in result.get("approaches", [])
        ],
        "plan_id": result.get("plan_id"),
    }
