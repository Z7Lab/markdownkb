"""MCTS tree node structure for plan exploration and evaluation."""

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlanNode:
    """A node in the MCTS planning tree representing a plan or sub-plan."""

    content: str
    node_type: str  # "root", "approach", "detail", "evaluation"
    parent: "PlanNode | None" = None
    children: list["PlanNode"] = field(default_factory=list)

    # MCTS stats
    visits: int = 0
    total_score: float = 0.0

    # Metadata
    sources: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> float:
        """Return the average score across all visits."""
        if self.visits == 0:
            return 0.0
        return self.total_score / self.visits

    @property
    def ucb1(self) -> float:
        """Compute the UCB1 value for node selection."""
        if self.visits == 0:
            return float("inf")
        if self.parent is None or self.parent.visits == 0:
            return self.score
        exploration = math.sqrt(2 * math.log(self.parent.visits) / self.visits)
        return self.score + exploration

    def add_child(self, content: str, node_type: str, **kwargs) -> "PlanNode":
        """Create and append a child node."""
        child = PlanNode(
            content=content,
            node_type=node_type,
            parent=self,
            **kwargs,
        )
        self.children.append(child)
        return child

    def backpropagate(self, score: float):
        """Propagate a score up the tree from this node to the root."""
        node: PlanNode | None = self
        while node is not None:
            node.visits += 1
            node.total_score += score
            node = node.parent

    def best_child(self) -> "PlanNode | None":
        """Return the child with the highest average score."""
        if not self.children:
            return None
        return max(self.children, key=lambda c: c.score)

    def select_child_ucb1(self) -> "PlanNode | None":
        """Return the child with the highest UCB1 value."""
        if not self.children:
            return None
        return max(self.children, key=lambda c: c.ucb1)

    def to_dict(self) -> dict:
        """Serialize the node and its subtree to a dictionary."""
        return {
            "content": self.content,
            "type": self.node_type,
            "score": round(self.score, 3),
            "visits": self.visits,
            "sources": self.sources,
            "children": [c.to_dict() for c in self.children],
        }

    def get_best_path(self) -> list["PlanNode"]:
        """Return the path from this node to the best leaf."""
        path = [self]
        current = self
        while current.children:
            best = current.best_child()
            if best is None:
                break
            path.append(best)
            current = best
        return path

    def flatten_plan(self) -> str:
        """Flatten the best path into a single plan string."""
        path = self.get_best_path()
        sections = []
        for node in path:
            if node.node_type == "root":
                continue
            sections.append(node.content)
        return "\n\n".join(sections)
