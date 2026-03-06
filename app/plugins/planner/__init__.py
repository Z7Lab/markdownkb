"""MCTS planner plugin — Monte Carlo Tree Search plan generation."""

from app.plugins.planner.router import router

FEATURE_FLAG = "mcts_planner"

__all__ = ["FEATURE_FLAG", "router"]
