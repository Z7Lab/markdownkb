"""Prompt templates for RAG, planning, and skill review."""

RAG_USER_TEMPLATE = """Context from your knowledge base:
---
{context}
---

Question: {question}"""

PLANNING_SYSTEM_PROMPT = (
    "You are mdkb in planning mode. Your job is to create "
    "precise implementation plans by analyzing the user's "
    "knowledge base, code, and patterns.\n\n"
    "Rules:\n"
    "- Research thoroughly before proposing solutions.\n"
    "- Reference specific files, functions, and patterns "
    "from the user's codebase.\n"
    "- Evaluate multiple approaches and explain trade-offs.\n"
    "- The output should be a detailed, actionable plan "
    "- not vague advice.\n"
    "- Always cite which documents/files informed each "
    "decision.\n"
    "- Match the user's existing patterns and stack choices.\n"
    "- Flag any potential issues "
    "(security, performance, compatibility)."
)

PLANNING_USER_TEMPLATE = """Knowledge base context:
---
{context}
---

Additional context from file exploration:
---
{exploration_context}
---

User's request: {request}

Create a detailed implementation plan based on the \
user's existing code and patterns."""

SKILL_REVIEW_TEMPLATE = (
    "You are a specialist reviewer with the following "
    "expertise:\n\n{skill_description}\n\n"
    "Review the following plan and provide specific, "
    "actionable feedback:\n\n"
    "Plan:\n---\n{plan}\n---\n\n"
    "Context from the knowledge base:\n"
    "---\n{context}\n---\n\n"
    "Provide your review with specific issues, "
    "suggestions, and approvals. Be concrete - reference "
    "specific files, patterns, and potential problems."
)


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
        "content": RAG_USER_TEMPLATE.format(
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
        {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
        {"role": "user", "content": PLANNING_USER_TEMPLATE.format(
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
        {"role": "user", "content": SKILL_REVIEW_TEMPLATE.format(
            skill_description=skill_description,
            plan=plan,
            context=context,
        )},
    ]
