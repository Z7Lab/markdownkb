"""LLM-powered query enhancement for intelligent search."""

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


QUERY_ENHANCEMENT_PROMPT = (
    "Extract search keywords from this query. "
    "Include the original terms plus any expanded forms of acronyms. "
    "For example, 'ENS' should become 'ENS Ethereum Name Service'. "
    "Return ONLY the keywords, no explanation. Keep it concise."
)


def enhance_query(
    query: str,
    settings: Settings | None = None,
) -> EnhancedQuery:
    """Use LLM to extract keywords, expand acronyms, and identify context."""
    settings = settings or Settings.get()

    # Skip enhancement for very short queries (3 words or less)
    if len(query.split()) <= 3:
        return EnhancedQuery(
            original=query,
            keywords=[],
            expanded_terms={},
            context="",
            error=None
        )

    # Build simple text-based prompt (same approach as chat's rewrite_query)
    messages = [
        {"role": "system", "content": QUERY_ENHANCEMENT_PROMPT},
        {"role": "user", "content": query},
    ]

    try:
        # Get LLM response (plain text, not JSON)
        response = get_completion(messages, settings)
        enhanced_text = response.strip().strip('"').strip("'")

        if enhanced_text and enhanced_text != query:
            logger.info("Query enhancement: %r -> %r", query[:80], enhanced_text[:80])
            # Store enhanced text in keywords for backward compatibility
            return EnhancedQuery(
                original=query,
                keywords=[enhanced_text],
                expanded_terms={},
                context="",
                error=None
            )

        # If LLM returned empty or same query, use original
        return EnhancedQuery(
            original=query,
            keywords=[],
            expanded_terms={},
            context="",
            error=None
        )

    except RuntimeError as e:
        # LLM offline
        logger.warning("Query enhancement failed (LLM offline): %s", e)
        return EnhancedQuery(
            original=query,
            keywords=[],
            expanded_terms={},
            context="",
            error=str(e),
        )
    except (OSError, ValueError) as e:
        logger.warning("Query enhancement IO/parsing error: %s", e)
        return EnhancedQuery(
            original=query,
            keywords=[],
            expanded_terms={},
            context="",
            error=str(e),
        )
    except (TypeError, AttributeError) as e:
        # Likely a code bug — log prominently and re-raise so it doesn't go unnoticed
        logger.error("Query enhancement unexpected error: %s", e, exc_info=True)
        raise


def build_enhanced_search_query(enhanced: EnhancedQuery) -> str:
    """Build search query from LLM-enhanced keywords."""
    # If we got enhanced keywords from LLM, use them (keywords[0] contains enhanced text)
    if enhanced.keywords and enhanced.keywords[0]:
        return enhanced.keywords[0]

    # Otherwise use original query
    return enhanced.original
