import logging
from typing import Any

from app.config import Settings
from app.mcp.filesystem import list_directory, read_file, format_tree
from app.planner.nodes import PlanNode
from app.planner.scoring import score_approach, extract_user_patterns
from app.rag.llm import get_completion
from app.rag.prompts import build_planning_messages
from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)

EXPANSION_PROMPT = """Based on the research context below, generate {n} distinct implementation approaches for the user's request.

Research context:
{context}

User's request: {request}

For each approach, provide:
1. A clear name/title
2. Key architectural decisions
3. Which existing code/patterns to reuse
4. Pros and cons

Format each approach as a separate numbered section."""

DETAIL_PROMPT = """Expand this approach into a detailed implementation plan:

Approach: {approach}

Known context:
{context}

User patterns/preferences: {patterns}

Provide:
1. Step-by-step implementation plan
2. Specific files to create/modify
3. Dependencies and libraries
4. Testing strategy
5. Potential issues and mitigations

Be specific — reference actual files, patterns, and code from the user's knowledge base."""


class MCTSPlanner:
    def __init__(self, retriever: Retriever, settings: Settings | None = None):
        self._retriever = retriever
        self._settings = settings or Settings.get()
        self._user_patterns: list[str] = []
        self._exploration_log: list[str] = []

    def plan(self, request: str, iterations: int = 3,
             n_approaches: int = 3) -> dict[str, Any]:
        self._exploration_log = []
        self._user_patterns = extract_user_patterns(self._retriever)

        # Phase 1: Research — search knowledge base
        logger.info("MCTS Phase 1: Research")
        research_results = self._research(request)

        # Phase 2: Explore — if MCP is enabled, explore filesystem
        exploration_context = ""
        if self._settings.feature_enabled("mcp_filesystem"):
            logger.info("MCTS Phase 2: Filesystem exploration")
            exploration_context = self._explore_filesystem(research_results)

        # Phase 3: Generate approaches
        logger.info("MCTS Phase 3: Generate approaches")
        root = PlanNode(content=request, node_type="root")
        self._expand(root, request, research_results, exploration_context,
                     n_approaches)

        # Phase 4: Evaluate and refine
        logger.info("MCTS Phase 4: Evaluate and refine")
        for i in range(iterations):
            logger.info(f"  Iteration {i+1}/{iterations}")
            self._iterate(root, request, research_results,
                          exploration_context)

        # Phase 5: Extract best plan
        best_plan = root.flatten_plan()
        best_path = root.get_best_path()

        # Collect all sources
        all_sources: list[str] = []
        for node in best_path:
            all_sources.extend(node.sources)
        unique_sources = list(dict.fromkeys(all_sources))

        return {
            "plan": best_plan,
            "tree": root.to_dict(),
            "sources": unique_sources,
            "exploration_log": self._exploration_log,
            "user_patterns": self._user_patterns,
            "iterations": iterations,
        }

    def _research(self, request: str) -> list[dict]:
        results = self._retriever.search(request, top_k=10)
        self._exploration_log.append(
            f"Searched knowledge base for: '{request}' — "
            f"found {len(results)} results"
        )
        return [
            {"document": r.document, "metadata": r.metadata, "score": r.score}
            for r in results
        ]

    def _explore_filesystem(self, research_results: list[dict]) -> str:
        explored: list[str] = []

        # Extract paths from research results
        paths_to_explore: set[str] = set()
        for r in research_results:
            source = r["metadata"].get("source_path", "")
            if source:
                from pathlib import Path
                parent = str(Path(source).parent)
                paths_to_explore.add(parent)

        for path in list(paths_to_explore)[:5]:  # Limit exploration
            try:
                tree = format_tree(path, max_depth=2)
                explored.append(f"Directory: {path}\n{tree}")
                self._exploration_log.append(f"Explored directory: {path}")
            except Exception as e:
                self._exploration_log.append(
                    f"Failed to explore {path}: {e}"
                )

        return "\n\n".join(explored)

    def _expand(self, root: PlanNode, request: str,
                research_results: list[dict], exploration_context: str,
                n_approaches: int):
        documents = [r["document"] for r in research_results]
        metadatas = [r["metadata"] for r in research_results]

        context = "\n\n".join(
            f"[{m.get('source_path', 'unknown')}]\n{d}"
            for d, m in zip(documents, metadatas)
        )

        prompt_content = EXPANSION_PROMPT.format(
            n=n_approaches, context=context, request=request,
        )

        messages = [
            {"role": "system",
             "content": "You are a planning assistant. Generate distinct approaches."},
            {"role": "user", "content": prompt_content},
        ]

        try:
            response = get_completion(messages, self._settings)
        except Exception as e:
            logger.error(f"LLM error during expansion: {e}")
            root.add_child(
                content=f"Default approach: {request}",
                node_type="approach",
            )
            return

        # Parse approaches from response
        approaches = self._parse_approaches(response)
        sources = [m.get("source_path", "") for m in metadatas if m.get("source_path")]

        for approach in approaches:
            node = root.add_child(
                content=approach,
                node_type="approach",
                sources=sources,
            )
            # Score and backpropagate
            s = score_approach(approach, request, self._retriever,
                               self._user_patterns)
            node.backpropagate(s)

    def _iterate(self, root: PlanNode, request: str,
                 research_results: list[dict], exploration_context: str):
        # Selection — pick most promising approach via UCB1
        selected = root.select_child_ucb1()
        if selected is None:
            return

        # Expansion — add detail to selected approach
        documents = [r["document"] for r in research_results[:5]]
        metadatas = [r["metadata"] for r in research_results[:5]]
        context = "\n\n".join(
            f"[{m.get('source_path', 'unknown')}]\n{d}"
            for d, m in zip(documents, metadatas)
        )

        prompt_content = DETAIL_PROMPT.format(
            approach=selected.content,
            context=context,
            patterns=", ".join(self._user_patterns[:20]),
        )

        messages = [
            {"role": "system",
             "content": "You are a planning assistant. Expand the approach into details."},
            {"role": "user", "content": prompt_content},
        ]

        try:
            response = get_completion(messages, self._settings)
        except Exception as e:
            logger.error(f"LLM error during iteration: {e}")
            return

        sources = [m.get("source_path", "") for m in metadatas if m.get("source_path")]
        detail_node = selected.add_child(
            content=response,
            node_type="detail",
            sources=sources,
        )

        # Score the detailed plan
        s = score_approach(response, request, self._retriever,
                           self._user_patterns)
        detail_node.backpropagate(s)

    def _parse_approaches(self, text: str) -> list[str]:
        import re
        # Split by numbered sections
        sections = re.split(r"\n(?=\d+\.?\s)", text)
        approaches = [s.strip() for s in sections if s.strip()]

        # If splitting didn't work, split by double newlines
        if len(approaches) <= 1:
            approaches = [p.strip() for p in text.split("\n\n\n")
                          if p.strip()]

        return approaches if approaches else [text]
