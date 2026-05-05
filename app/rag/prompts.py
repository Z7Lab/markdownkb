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


def get_skill_review_template() -> str:
    return _get("skill_review")


# ---------------------------------------------------------------------------
# Context formatting and message builders
# ---------------------------------------------------------------------------

def format_context(
    documents: list[str], metadatas: list[dict]
) -> tuple[str, dict[str, str]]:
    """Format documents with numbered source references.

    Returns ``(context_string, source_map)`` where *source_map* maps
    reference numbers to absolute file paths, e.g. ``{"1": "/data/a.md"}``.
    Multiple chunks from the same file share the same reference number.
    """
    source_map: dict[str, str] = {}   # "1" -> path
    path_to_num: dict[str, str] = {}  # path -> "1"
    counter = 0
    parts: list[str] = []

    for doc, meta in zip(documents, metadatas):
        source = meta.get("source_path", "unknown")
        heading = meta.get("heading", "")

        if source not in path_to_num:
            counter += 1
            num = str(counter)
            path_to_num[source] = num
            source_map[num] = source

        ref = path_to_num[source]
        header = f"[{ref}] Source: {source}"
        if heading:
            header += f" | Section: {heading}"
        parts.append(f"{header}\n{doc}")

    return "\n\n---\n\n".join(parts), source_map


def build_rag_messages(
    question: str,
    documents: list[str],
    metadatas: list[dict],
    conversation_history: list[dict] | None = None,
    system_prompt: str = "",
) -> tuple[list[dict], dict[str, str]]:
    """Build the message list for a RAG completion request.

    Returns ``(messages, source_map)`` where *source_map* maps reference
    numbers (``"1"``, ``"2"``, …) to absolute source file paths.
    """
    context, source_map = format_context(documents, metadatas)

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

    return messages, source_map


def build_skill_review_messages(
    plan: str,
    skill_description: str,
    documents: list[str],
    metadatas: list[dict],
) -> list[dict]:
    """Build the message list for a skill-based plan review."""
    context, _ = format_context(documents, metadatas)
    return [
        {"role": "system",
         "content": "You are a specialist plan reviewer."},
        {"role": "user", "content": get_skill_review_template().format(
            skill_description=skill_description,
            plan=plan,
            context=context,
        )},
    ]
