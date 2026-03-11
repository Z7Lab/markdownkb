"""Deep research service — MCTS-powered multi-angle search synthesis.

Generic service that any tab (search, chat, graph, etc.) can use.
Runs the MCTS pipeline to explore multiple research angles, then
synthesizes a comprehensive summary grounded in the best path.
"""

import logging
from typing import Generator

from app.config import Settings
from app.planner.mcts import MCTSPlanner
from app.rag.llm import get_streaming_completion
from app.rag.prompts import format_context
from app.rag.retriever import Retriever
from app.services.chat_service import extract_unique_sources, strip_thinking
from app.utils import sse

logger = logging.getLogger(__name__)

DEEP_RESEARCH_SYSTEM = (
    "You are a research synthesis assistant. You have explored multiple "
    "research angles on the user's query using a tree-search process. "
    "Below you are given:\n"
    "1. The original query\n"
    "2. The best research path (multiple angles explored and refined)\n"
    "3. Source documents from the knowledge base\n\n"
    "Synthesize a comprehensive, well-structured answer that:\n"
    "- Addresses the query thoroughly from multiple angles\n"
    "- Cites specific sources where relevant\n"
    "- Highlights key findings and trade-offs discovered\n"
    "- Is more detailed than a standard summary, since the user "
    "explicitly requested deep research"
)

DEEP_RESEARCH_USER = (
    "Query: {query}\n\n"
    "Research exploration (best path through {iterations} iterations, "
    "{n_approaches} approaches evaluated):\n"
    "---\n{plan}\n---\n\n"
    "Source documents:\n---\n{context}\n---\n\n"
    "Provide a comprehensive synthesis answering the query, citing sources."
)


_DEFAULTS = {
    "iterations": 3,
    "n_approaches": 3,
}


def get_deep_research_config(settings: Settings) -> dict:
    """Return deep research config with defaults applied."""
    return {**_DEFAULTS, **settings.get_plugin_config("deep_research")}


def stream_deep_research(
    query: str,
    retriever: Retriever,
    settings: Settings,
    *,
    iterations: int | None = None,
    n_approaches: int | None = None,
    folders_filter: list[str] | None = None,
    allowed_paths: set[str] | None = None,
    search_id: str | None = None,
) -> Generator[str, None, None]:
    """Run MCTS deep research and stream the synthesis as SSE events.

    Yields SSE events compatible with the existing summary stream format
    (status, sources, token, done) so the frontend can consume it with
    the same callbacks.
    """
    # Resolve config defaults
    cfg = get_deep_research_config(settings)
    if iterations is None:
        iterations = cfg["iterations"]
    if n_approaches is None:
        n_approaches = cfg["n_approaches"]

    yield sse("status", {
        "phase": "research",
        "message": "Starting deep research...",
        "iteration": 0,
        "total_iterations": iterations,
    })

    # Phase 1-4: Run MCTS planner
    planner = MCTSPlanner(retriever, settings)
    planner._folders_filter = folders_filter
    planner._allowed_paths = allowed_paths

    yield sse("status", {
        "phase": "research",
        "message": "Searching knowledge base...",
        "iteration": 0,
        "total_iterations": iterations,
    })
    planner._exploration_log = []
    planner._user_patterns = []
    planner._research_results = planner._research(query)

    yield sse("status", {
        "phase": "expand",
        "message": f"Generating {n_approaches} research angles...",
        "iteration": 0,
        "total_iterations": iterations,
    })

    from app.planner.nodes import PlanNode
    root = PlanNode(content=query, node_type="root")
    planner._expand(root, query, n_approaches)

    yield sse("status", {
        "phase": "expand",
        "message": f"Evaluating {len(root.children)} angles...",
        "iteration": 0,
        "total_iterations": iterations,
    })

    for i in range(iterations):
        yield sse("status", {
            "phase": "iterate",
            "message": f"Deepening research ({i + 1}/{iterations})...",
            "iteration": i + 1,
            "total_iterations": iterations,
        })
        planner._iterate(root, query)

    # Phase 5: Extract best plan and sources
    best_plan = root.flatten_plan()
    best_path = root.get_best_path()

    all_sources: list[str] = []
    for node in best_path:
        all_sources.extend(node.sources)
    unique_sources = list(dict.fromkeys(s for s in all_sources if s))

    yield sse("sources", {"sources": unique_sources})

    # Build context from research results for the synthesis prompt
    documents = [r["document"] for r in planner._research_results[:10]]
    metadatas = [r["metadata"] for r in planner._research_results[:10]]
    context = format_context(documents, metadatas)

    # Phase 6: Stream the synthesis
    yield sse("status", {
        "phase": "synthesize",
        "message": "Synthesizing findings...",
        "iteration": iterations,
        "total_iterations": iterations,
    })

    messages = [
        {"role": "system", "content": DEEP_RESEARCH_SYSTEM},
        {"role": "user", "content": DEEP_RESEARCH_USER.format(
            query=query,
            plan=best_plan,
            context=context,
            iterations=iterations,
            n_approaches=n_approaches,
        )},
    ]

    raw = ""
    last_yielded = ""
    try:
        for chunk in get_streaming_completion(messages, settings):
            raw += chunk
            cleaned = strip_thinking(raw)
            if cleaned != last_yielded:
                delta = cleaned[len(last_yielded):]
                if delta:
                    yield sse("token", {"content": delta})
                    last_yielded = cleaned
    except RuntimeError as e:
        logger.error("Deep research synthesis error: %s", e)
        yield sse("error", {
            "message": "Deep research synthesis failed. Check server logs.",
        })

    # Emit full summary text so callers can persist it without parsing tokens
    if last_yielded:
        yield sse("summary_text", {"text": last_yielded})

    yield sse("done", {})
