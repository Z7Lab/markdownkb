"""Service layer for the MCTS planner and agent skills."""

import logging
from dataclasses import asdict
from typing import Any, Generator

from app.config import Settings
from app.planner.mcts import MCTSPlanner
from app.planner.scoring import extract_user_patterns, score_approach
from app.rag.retriever import Retriever
from app.skills.executor import (
    refine_plan_with_reviews,
    run_multi_skill_review,
)
from app.skills.loader import discover_skills
from app.utils import sse

logger = logging.getLogger(__name__)


def run_planner(
    request: str,
    retriever: Retriever,
    settings: Settings,
    iterations: int = 3,
    n_approaches: int = 3,
    skill_names: list[str] | None = None,
    folders_filter: list[str] | None = None,
    allowed_paths: set[str] | None = None,
) -> dict[str, Any]:
    """Run the MCTS planner and optionally refine with skill reviews."""
    planner = MCTSPlanner(retriever, settings)
    planner._folders_filter = folders_filter
    planner._allowed_paths = allowed_paths
    result = planner.plan(request, iterations, n_approaches)

    if skill_names and settings.core_enabled("agent_skills"):
        reviews = run_multi_skill_review(
            result["plan"], skill_names, retriever, settings,
        )
        refined = refine_plan_with_reviews(
            result["plan"], reviews, settings,
        )
        result["reviews"] = [asdict(r) for r in reviews]
        result["refined_plan"] = refined

    return result


def stream_planner(
    request: str,
    retriever: Retriever,
    settings: Settings,
    iterations: int = 3,
    n_approaches: int = 3,
    skill_names: list[str] | None = None,
    folders_filter: list[str] | None = None,
    allowed_paths: set[str] | None = None,
) -> Generator[str, None, None]:
    """Stream planner progress as SSE events.

    Accesses single-underscore methods on MCTSPlanner to provide granular
    phase-level progress. This is intentional coupling documented here.
    """
    planner = MCTSPlanner(retriever, settings)
    planner._folders_filter = folders_filter
    planner._allowed_paths = allowed_paths
    planner._exploration_log = []
    planner._user_patterns = extract_user_patterns(retriever)

    # Phase 1: Research
    yield sse("status", {"phase": "research", "message": "Searching knowledge base..."})
    planner._research_results = planner._research(request)

    # Phase 2: Filesystem exploration (optional)
    planner._exploration_context = ""
    if settings.mcp_enabled("filesystem"):
        yield sse("status", {"phase": "explore", "message": "Exploring filesystem..."})
        planner._exploration_context = planner._explore_filesystem(
            planner._research_results,
        )

    # Phase 3: Generate approaches
    yield sse("status", {"phase": "expand", "message": f"Generating {n_approaches} approaches (waiting for LLM)..."})
    from app.planner.nodes import PlanNode
    root = PlanNode(content=request, node_type="root")
    planner._expand(root, request, n_approaches)

    yield sse("status", {"phase": "expand", "message": f"Scoring {len(root.children)} approaches..."})

    # Emit each approach
    for child in root.children:
        yield sse("approach", {
            "content": child.content,
            "score": round(child.score, 3),
        })

    # Phase 4: Iterate
    for i in range(iterations):
        yield sse("status", {
            "phase": "iterate",
            "message": f"Deepening analysis ({i + 1}/{iterations}) — expanding best approach...",
        })
        planner._iterate(root, request)

    # Phase 5: Extract best plan
    yield sse("status", {"phase": "plan", "message": "Synthesizing implementation plan..."})
    best_plan = root.flatten_plan()
    best_path = root.get_best_path()

    all_sources: list[str] = []
    for node in best_path:
        all_sources.extend(node.sources)
    unique_sources = list(dict.fromkeys(all_sources))

    yield sse("plan", {"plan": best_plan})
    yield sse("sources", {"sources": unique_sources})
    yield sse("tree", {"tree": root.to_dict()})

    # Optional: Skill reviews
    if skill_names and settings.core_enabled("agent_skills"):
        yield sse("status", {"phase": "review", "message": "Running skill reviews..."})
        reviews = run_multi_skill_review(
            best_plan, skill_names, retriever, settings,
        )
        refined = refine_plan_with_reviews(best_plan, reviews, settings)
        yield sse("reviews", {
            "reviews": [asdict(r) for r in reviews],
            "refined_plan": refined,
        })

    yield sse("done", {})


def list_skills() -> list[dict[str, str]]:
    """Return all discovered skills with their metadata."""
    skills = discover_skills()
    return [
        {"name": s.name, "description": s.description, "source": s.source}
        for s in skills
    ]
