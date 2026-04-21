"""Monte Carlo Tree Search planner for deep research and plan generation."""

import logging
import re
from typing import Any

from app.config import Settings
from app.planner.nodes import PlanNode
from app.planner.scoring import score_approach, extract_user_patterns
from app.rag.llm import get_completion
from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)

EXPANSION_PROMPT = (
    "Based on the research context below, generate {n} distinct "
    "implementation approaches for the user's request.\n\n"
    "Research context:\n{context}\n\n"
    "User's request: {request}\n\n"
    "For each approach, provide:\n"
    "1. A clear name/title\n"
    "2. Key architectural decisions\n"
    "3. Which existing code/patterns to reuse\n"
    "4. Pros and cons\n\n"
    "Format each approach as a separate numbered section."
)

DETAIL_PROMPT = (
    "Expand this approach into a detailed implementation plan:"
    "\n\nApproach: {approach}\n\n"
    "Known context:\n{context}\n\n"
    "User patterns/preferences: {patterns}\n\n"
    "Provide:\n"
    "1. Step-by-step implementation plan\n"
    "2. Specific files to create/modify\n"
    "3. Dependencies and libraries\n"
    "4. Testing strategy\n"
    "5. Potential issues and mitigations\n\n"
    "Be specific - reference actual files, patterns, and code "
    "from the user's knowledge base."
)


class MCTSPlanner:
    """MCTS planner that generates and evaluates implementation plans."""

    def __init__(self, retriever: Retriever,
                 settings: Settings | None = None,
                 folders_filter: list[str] | None = None,
                 allowed_paths: set[str] | None = None):
        self._retriever = retriever
        self._settings = settings or Settings.get()
        self._user_patterns: list[str] = []
        self._exploration_log: list[str] = []
        self._research_results: list[dict] = []
        self._folders_filter = folders_filter
        self._allowed_paths = allowed_paths
        self._exclude_patterns: list[str] | None = None
        self._bucket_retriever = None
        self._kgdb = None
        self._kg_context = ""

    def plan(self, request: str, iterations: int = 3,
             n_approaches: int = 3) -> dict[str, Any]:
        """Run the full MCTS planning pipeline."""
        self._exploration_log = []
        self._user_patterns = extract_user_patterns(
            self._retriever
        )

        # Phase 1: Research -- search knowledge base
        logger.info("MCTS Phase 1: Research")
        self._research_results = self._research(request)

        # Phase 2: Generate approaches
        logger.info("MCTS Phase 2: Generate approaches")
        root = PlanNode(content=request, node_type="root")
        self._expand(root, request, n_approaches)

        # Phase 3: Evaluate and refine
        logger.info("MCTS Phase 3: Evaluate and refine")
        for i in range(iterations):
            logger.info("  Iteration %d/%d", i + 1, iterations)
            self._iterate(root, request)

        # Phase 4: Extract best plan
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

    # -- Public API for step-by-step usage (e.g. deep_research) --

    @property
    def research_results(self) -> list[dict]:
        """Return the research results from the last research phase."""
        return self._research_results

    @research_results.setter
    def research_results(self, value: list[dict]):
        self._research_results = value

    def research(self, request: str) -> list[dict]:
        """Search the knowledge base for relevant context."""
        return self._research(request)

    def expand(self, root: "PlanNode", request: str,
               n_approaches: int):
        """Generate initial approach nodes under the root."""
        self._expand(root, request, n_approaches)

    def iterate(self, root: "PlanNode", request: str):
        """Run one MCTS iteration: select, expand, evaluate."""
        self._iterate(root, request)

    def _research(self, request: str) -> list[dict]:
        """Search the knowledge base for relevant context."""
        results = self._retriever.search(
            request, top_k=10, folders_filter=self._folders_filter,
            allowed_paths=self._allowed_paths,
            exclude_patterns=self._exclude_patterns,
        )
        # Merge bucket results for combined scope+bucket queries
        if self._bucket_retriever:
            bucket_results = self._bucket_retriever.search(request, top_k=10)
            for r in bucket_results:
                r.metadata["_bucket"] = "true"
            results = sorted(results + bucket_results, key=lambda r: r.score, reverse=True)[:10]
        self._exploration_log.append(
            f"Searched knowledge base for: '{request}' -- "
            f"found {len(results)} results"
        )
        if self._kgdb is not None:
            self._kg_context = self._kgdb.context_for_query(request)
        return [
            {
                "document": r.document,
                "metadata": r.metadata,
                "score": r.score,
            }
            for r in results
        ]

    def _build_context(
        self, research_results: list[dict]
    ) -> tuple[str, list[dict]]:
        """Build context string from research results."""
        documents = [r["document"] for r in research_results]
        metadatas = [r["metadata"] for r in research_results]

        context = "\n\n".join(
            f"[{m.get('source_path', 'unknown')}]\n{d}"
            for d, m in zip(documents, metadatas)
        )
        if self._kg_context:
            context += "\n\n" + self._kg_context

        return context, metadatas

    def _expand(self, root: PlanNode, request: str,
                n_approaches: int):
        """Generate initial approach nodes under the root."""
        context, metadatas = self._build_context(
            self._research_results
        )

        prompt_content = EXPANSION_PROMPT.format(
            n=n_approaches, context=context, request=request,
        )

        messages = [
            {"role": "system",
             "content": "You are a planning assistant. "
                        "Generate distinct approaches."},
            {"role": "user", "content": prompt_content},
        ]

        try:
            response = get_completion(messages, self._settings)
        except RuntimeError as e:
            logger.error("LLM error during expansion: %s", e)
            root.add_child(
                content=f"Default approach: {request}",
                node_type="approach",
            )
            return

        approaches = self._parse_approaches(response)
        sources = [
            m.get("source_path", "")
            for m in metadatas if m.get("source_path")
        ]

        for approach in approaches:
            node = root.add_child(
                content=approach,
                node_type="approach",
                sources=sources,
            )
            score = score_approach(
                approach, request,
                self._retriever, self._user_patterns,
            )
            node.backpropagate(score)

    def _iterate(self, root: PlanNode, request: str):
        """Run one MCTS iteration: select, expand, evaluate."""
        selected = root.select_child_ucb1()
        if selected is None:
            return

        results_slice = self._research_results[:5]
        context, metadatas = self._build_context(results_slice)

        prompt_content = DETAIL_PROMPT.format(
            approach=selected.content,
            context=context,
            patterns=", ".join(self._user_patterns[:20]),
        )

        messages = [
            {"role": "system",
             "content": "You are a planning assistant. "
                        "Expand the approach into details."},
            {"role": "user", "content": prompt_content},
        ]

        try:
            response = get_completion(messages, self._settings)
        except RuntimeError as e:
            logger.error("LLM error during iteration: %s", e)
            return

        sources = [
            m.get("source_path", "")
            for m in metadatas if m.get("source_path")
        ]
        detail_node = selected.add_child(
            content=response,
            node_type="detail",
            sources=sources,
        )

        score = score_approach(
            response, request,
            self._retriever, self._user_patterns,
        )
        detail_node.backpropagate(score)

    def _parse_approaches(self, text: str) -> list[str]:
        """Parse numbered approach sections from LLM response."""
        sections = re.split(r"\n(?=\d+\.?\s)", text)
        approaches = [s.strip() for s in sections if s.strip()]

        if len(approaches) <= 1:
            approaches = [
                p.strip() for p in text.split("\n\n\n")
                if p.strip()
            ]

        return approaches if approaches else [text]
