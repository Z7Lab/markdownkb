RAG_SYSTEM_PROMPT = """You are mdkb, a personal knowledge base assistant. You answer questions based on the user's indexed markdown documents.

Rules:
- Answer ONLY based on the provided context. If the context doesn't contain enough information, say so.
- Always cite your sources at the end of your response using the format: Source: <file path>
- When synthesizing information from multiple files, cite all relevant sources.
- Be concise but thorough. Summarize across multiple documents when relevant.
- If the user asks about something not in the context, say "I don't have information about that in your knowledge base."
- Preserve technical accuracy — don't paraphrase code or configuration incorrectly.
- Use markdown formatting in your responses."""

RAG_USER_TEMPLATE = """Context from your knowledge base:
---
{context}
---

Question: {question}"""

PLANNING_SYSTEM_PROMPT = """You are mdkb in planning mode. Your job is to create precise implementation plans by analyzing the user's knowledge base, code, and patterns.

Rules:
- Research thoroughly before proposing solutions.
- Reference specific files, functions, and patterns from the user's codebase.
- Evaluate multiple approaches and explain trade-offs.
- The output should be a detailed, actionable plan — not vague advice.
- Always cite which documents/files informed each decision.
- Match the user's existing patterns and stack choices.
- Flag any potential issues (security, performance, compatibility)."""

PLANNING_USER_TEMPLATE = """Knowledge base context:
---
{context}
---

Additional context from file exploration:
---
{exploration_context}
---

User's request: {request}

Create a detailed implementation plan based on the user's existing code and patterns."""

SKILL_REVIEW_TEMPLATE = """You are a specialist reviewer with the following expertise:

{skill_description}

Review the following plan and provide specific, actionable feedback:

Plan:
---
{plan}
---

Context from the knowledge base:
---
{context}
---

Provide your review with specific issues, suggestions, and approvals. Be concrete — reference specific files, patterns, and potential problems."""


def format_context(documents: list[str], metadatas: list[dict]) -> str:
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


def build_rag_messages(question: str, documents: list[str],
                       metadatas: list[dict],
                       conversation_history: list[dict] | None = None) -> list[dict]:
    context = format_context(documents, metadatas)

    messages: list[dict] = [{"role": "system", "content": RAG_SYSTEM_PROMPT}]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({
        "role": "user",
        "content": RAG_USER_TEMPLATE.format(context=context, question=question),
    })

    return messages


def build_planning_messages(request: str, documents: list[str],
                            metadatas: list[dict],
                            exploration_context: str = "") -> list[dict]:
    context = format_context(documents, metadatas)
    return [
        {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
        {"role": "user", "content": PLANNING_USER_TEMPLATE.format(
            context=context,
            exploration_context=exploration_context or "N/A",
            request=request,
        )},
    ]


def build_skill_review_messages(plan: str, skill_description: str,
                                documents: list[str],
                                metadatas: list[dict]) -> list[dict]:
    context = format_context(documents, metadatas)
    return [
        {"role": "system", "content": "You are a specialist plan reviewer."},
        {"role": "user", "content": SKILL_REVIEW_TEMPLATE.format(
            skill_description=skill_description,
            plan=plan,
            context=context,
        )},
    ]
