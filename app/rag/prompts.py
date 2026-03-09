"""Prompt templates for RAG, planning, skill review, and search summary.

All templates are loaded from ``config/prompts/{name}.md``.
Edit those files to customise prompts without touching code.
"""

from app.config import Settings


def _get(name: str) -> str:
    return Settings.get().get_prompt(name)


# ---------------------------------------------------------------------------
# Public accessors
# ---------------------------------------------------------------------------

def get_system_prompt() -> str:
    return _get("system")


def get_search_summary_system() -> str:
    return _get("search_summary_system")


def get_search_summary_user() -> str:
    return _get("search_summary_user")


def get_query_rewrite_prompt() -> str:
    return _get("query_rewrite")


def get_rag_user_template() -> str:
    return _get("rag_user")


def get_planning_system_prompt() -> str:
    return _get("planning_system")


def get_planning_user_template() -> str:
    return _get("planning_user")


def get_skill_review_template() -> str:
    return _get("skill_review")


# ---------------------------------------------------------------------------
# Context formatting and message builders
# ---------------------------------------------------------------------------

def format_context(
    documents: list[str], metadatas: list[dict]
) -> str:
    """Format documents and metadata into a context string."""
    parts: list[str] = []
    for doc, meta in zip(documents, metadatas):
        source = meta.get("source_path", "unknown")
        heading = meta.get("heading", "")
        header = f"[Source: {source}"
        if heading:
            header += f" | Section: {heading}"
        header += "]"
        parts.append(f"{header}\n{doc}")
    return "\n\n---\n\n".join(parts)


def build_rag_messages(
    question: str,
    documents: list[str],
    metadatas: list[dict],
    conversation_history: list[dict] | None = None,
    system_prompt: str = "",
) -> list[dict]:
    """Build the message list for a RAG completion request."""
    context = format_context(documents, metadatas)

    messages: list[dict] = [
        {"role": "system", "content": system_prompt}
    ]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({
        "role": "user",
        "content": get_rag_user_template().format(
            context=context, question=question
        ),
    })

    return messages


def build_planning_messages(
    request: str,
    documents: list[str],
    metadatas: list[dict],
    exploration_context: str = "",
) -> list[dict]:
    """Build the message list for a planning request."""
    context = format_context(documents, metadatas)
    return [
        {"role": "system", "content": get_planning_system_prompt()},
        {"role": "user", "content": get_planning_user_template().format(
            context=context,
            exploration_context=exploration_context or "N/A",
            request=request,
        )},
    ]


def build_skill_review_messages(
    plan: str,
    skill_description: str,
    documents: list[str],
    metadatas: list[dict],
) -> list[dict]:
    """Build the message list for a skill-based plan review."""
    context = format_context(documents, metadatas)
    return [
        {"role": "system",
         "content": "You are a specialist plan reviewer."},
        {"role": "user", "content": get_skill_review_template().format(
            skill_description=skill_description,
            plan=plan,
            context=context,
        )},
    ]
