"""Scoring functions for evaluating plan approaches."""

import logging
import re

from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)


def score_approach(
    approach: str, query: str, retriever: Retriever,
    user_patterns: list[str] | None = None,
) -> float:
    """Score a plan approach on relevance, specificity, patterns, and actionability."""
    scores: list[float] = []

    # 1. Relevance to query (via retrieval similarity)
    relevance = _score_relevance(approach, query, retriever)
    scores.append(relevance * 0.3)

    # 2. Specificity — more concrete details score higher
    specificity = _score_specificity(approach)
    scores.append(specificity * 0.2)

    # 3. Pattern matching — does this match user's patterns?
    if user_patterns:
        pattern_score = _score_pattern_match(
            approach, user_patterns
        )
        scores.append(pattern_score * 0.3)
    else:
        scores.append(0.15)  # neutral if no patterns

    # 4. Actionability — can this be directly implemented?
    actionability = _score_actionability(approach)
    scores.append(actionability * 0.2)

    return sum(scores)


def _score_relevance(
    text: str, query: str, retriever: Retriever,
) -> float:
    """Score relevance of approach text to the query and KB."""
    combined = f"{query}\n\n{text[:500]}"
    results = retriever.search(combined, top_k=3)
    if not results:
        return 0.0
    return sum(r.score for r in results) / len(results)


def _score_specificity(text: str) -> float:
    """Score how specific and concrete the text is."""
    indicators = [
        r"\b\w+\.\w+\b",       # file.ext references
        r"`[^`]+`",             # code references
        r"\b(import|from|require|using)\b",
        r"\b\d+\.\d+\.\d+\b",  # version numbers
        r"\b(src|lib|app|config|test)/",
    ]

    score = 0.0
    for pattern in indicators:
        matches = re.findall(pattern, text)
        score += min(len(matches) * 0.1, 0.3)

    return min(score, 1.0)


def _score_pattern_match(
    text: str, patterns: list[str]
) -> float:
    """Score how well the text matches known user patterns."""
    text_lower = text.lower()
    matches = sum(1 for p in patterns if p.lower() in text_lower)
    if not patterns:
        return 0.5
    return min(matches / len(patterns), 1.0)


def _score_actionability(text: str) -> float:
    """Score how actionable and implementation-ready the text is."""
    action_indicators = [
        r"^\s*\d+\.",           # numbered steps
        r"^\s*[-*]",            # bullet points
        r"\b(create|add|modify|update|implement|write|configure)\b",
        r"\b(file|directory|module|class|function|endpoint)\b",
    ]

    score = 0.0
    for pattern in action_indicators:
        if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
            score += 0.25

    return min(score, 1.0)


def extract_user_patterns(retriever: Retriever) -> list[str]:
    """Extract technology and tool patterns from the KB."""
    patterns: set[str] = set()

    all_meta = retriever.get_all_metadatas()
    for meta in all_meta:
        tags = meta.get("tags", "")
        if tags:
            for tag in tags.split(", "):
                if tag.strip():
                    patterns.add(tag.strip())

    # Search for common tech stack indicators
    tech_re = (
        r"\b(React|Next\.js|Vue|Angular|Express|"
        r"FastAPI|Django|Flask|"
        r"TypeScript|Python|Rust|Go|Solidity|"
        r"PostgreSQL|MongoDB|Redis|ChromaDB|"
        r"Docker|Kubernetes|AWS|GCP|"
        r"Jest|Vitest|Pytest|Foundry|Hardhat|"
        r"ethers|wagmi|viem)\b"
    )
    for query in ["stack", "framework", "library", "pattern"]:
        results = retriever.search(query, top_k=3)
        for r in results:
            tech_matches = re.findall(
                tech_re, r.document, re.IGNORECASE,
            )
            patterns.update(tech_matches)

    return list(patterns)
