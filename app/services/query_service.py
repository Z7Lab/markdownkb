"""LLM-powered query enhancement for intelligent search."""

import json
import logging
from dataclasses import dataclass

from app.config import Settings
from app.rag.llm import get_completion

logger = logging.getLogger(__name__)


@dataclass
class EnhancedQuery:
    """Result of LLM query enhancement."""

    original: str
    keywords: list[str]  # Critical keywords that must appear
    expanded_terms: dict[str, str]  # Acronym -> expanded form
    context: str  # Semantic context/domain
    error: str | None = None  # If LLM failed


QUERY_ENHANCEMENT_PROMPT = """You are a search query analyzer. Given a user's search query, extract structured information to improve search results.

User query: "{query}"

Please analyze this query and return a JSON object with:
- "keywords": List of critical terms that MUST appear in results (e.g., specific names, acronyms, technical terms)
- "expanded_terms": Dictionary mapping acronyms to their full forms (e.g., {{"ENS": "Ethereum Name Service"}})
- "context": Short description of the semantic domain/topic (e.g., "blockchain naming systems", "AI coding strategies")

Rules:
- Keywords should be specific, not generic (e.g., "ENS" is critical, "AI" might not be)
- Only expand acronyms you're confident about
- Context should be 3-5 words describing the topic domain
- Return ONLY valid JSON, no other text

Example for query "what is a good idea with ENS and AI":
{{
  "keywords": ["ENS", "Ethereum Name Service"],
  "expanded_terms": {{"ENS": "Ethereum Name Service"}},
  "context": "blockchain naming with AI"
}}

Now analyze the user's query and return JSON:"""


def enhance_query(
    query: str,
    settings: Settings | None = None,
) -> EnhancedQuery:
    """Use LLM to extract keywords, expand acronyms, and identify context."""
    settings = settings or Settings.get()

    # Build the prompt
    prompt = QUERY_ENHANCEMENT_PROMPT.format(query=query)
    messages = [{"role": "user", "content": prompt}]

    try:
        # Get LLM response
        response = get_completion(messages, settings, temperature=0.0)

        # Parse JSON response
        # Strip markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            # Remove ```json or ``` wrapper
            lines = response.split("\n")
            response = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            )

        data = json.loads(response)

        enhanced = EnhancedQuery(
            original=query,
            keywords=data.get("keywords", []),
            expanded_terms=data.get("expanded_terms", {}),
            context=data.get("context", ""),
        )
        logger.info("Query enhancement successful: %s -> keywords=%s, expansions=%s",
                   query, enhanced.keywords, enhanced.expanded_terms)
        return enhanced

    except RuntimeError as e:
        # LLM is actually offline/unavailable
        logger.warning("LLM unavailable for query enhancement: %s", e)
        return EnhancedQuery(
            original=query,
            keywords=[],
            expanded_terms={},
            context="",
            error=str(e),
        )
    except json.JSONDecodeError as e:
        # LLM responded but we couldn't parse it - don't show "offline" toast
        logger.warning("Failed to parse LLM response for query enhancement: %s. Response: %s", e, response)
        return EnhancedQuery(
            original=query,
            keywords=[],
            expanded_terms={},
            context="",
            error=None,  # Don't show offline toast for parsing errors
        )
    except (KeyError, TypeError, AttributeError) as e:
        # Unexpected error in processing - fall back silently without "offline" toast
        logger.warning("Unexpected error in query enhancement: %s", e)
        return EnhancedQuery(
            original=query,
            keywords=[],
            expanded_terms={},
            context="",
            error=None,
        )


def build_enhanced_search_query(enhanced: EnhancedQuery) -> str:
    """Build an optimized search string from enhanced query data."""
    parts = [enhanced.original]

    # Add expanded terms to boost recall
    for acronym, expansion in enhanced.expanded_terms.items():
        if expansion not in enhanced.original:
            parts.append(expansion)

    # Add context for semantic enrichment
    if enhanced.context and enhanced.context not in enhanced.original:
        parts.append(enhanced.context)

    return " ".join(parts)
