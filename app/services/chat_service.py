"""Chat business logic: conversation memory, streaming RAG, plan saving."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Generator

from app.config import Settings
from app.rag.llm import get_completion, get_streaming_completion
from app.rag.prompts import QUERY_REWRITE_PROMPT, build_rag_messages
from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)

import re

MAX_HISTORY = 20
REPEAT_WINDOW = 150

# Matches <think>...</think> blocks (qwen3, deepseek, etc.)
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>[\s:]*", re.IGNORECASE)
# Matches an unclosed <think> tag at the end of streaming text
_THINK_OPEN_RE = re.compile(r"<think>[\s\S]*$", re.IGNORECASE)


class ConversationHistory:
    """Thread-safe conversation memory for chat context."""

    def __init__(self):
        self._history: list[dict] = []

    def add(self, role: str, content: str):
        """Append a message and trim if over limit."""
        self._history.append({"role": role, "content": content})
        if len(self._history) > MAX_HISTORY * 2:
            self._history = self._history[-(MAX_HISTORY * 2):]

    def get_history(self) -> list[dict]:
        """Return the recent conversation history."""
        return list(self._history[-(MAX_HISTORY * 2):])

    def clear(self):
        """Clear all conversation history."""
        self._history = []


conversation_history = ConversationHistory()


def _is_repeating(text: str) -> bool:
    """Check if the response has entered a repetition loop."""
    if len(text) < REPEAT_WINDOW * 2:
        return False
    tail = text[-REPEAT_WINDOW:]
    return tail in text[:-REPEAT_WINDOW]


def _truncate_at_repeat(text: str) -> str:
    """Cut text where it starts repeating."""
    tail = text[-REPEAT_WINDOW:]
    first = text.find(tail)
    if 0 <= first < len(text) - REPEAT_WINDOW:
        second = text.find(tail, first + 1)
        if second > first:
            cut = text.rfind("\n\n", first + REPEAT_WINDOW, second)
            if cut > 0:
                return text[:cut].rstrip()
            return text[:second].rstrip()
    return text


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks from model output."""
    # Strip completed thinking blocks
    text = _THINK_RE.sub("", text)
    # Strip unclosed thinking block at the end (still streaming)
    text = _THINK_OPEN_RE.sub("", text)
    return text


def _strip_source_block(text: str) -> str:
    """Remove source citations before storing in history."""
    for marker in ("\n\n---\n**Sources:**", "\n\nSource: "):
        idx = text.find(marker)
        if idx >= 0:
            return text[:idx].rstrip()
    return text


def extract_unique_sources(metadatas: list[dict]) -> list[str]:
    """Extract deduplicated source file paths from metadata list."""
    seen = set()
    sources = []
    for m in metadatas:
        src = m.get("source_path", "")
        if src and src not in seen:
            seen.add(src)
            sources.append(src)
    return sources


def _persist(chatdb, thread_id: str | None, user_msg: str, assistant_msg: str):
    """Save user + assistant messages to the thread DB."""
    if thread_id and chatdb:
        chatdb.add_message(thread_id, "user", user_msg)
        chatdb.add_message(thread_id, "assistant", assistant_msg)
    else:
        conversation_history.add("user", user_msg)
        conversation_history.add("assistant", assistant_msg)


_REWRITE_THRESHOLD = 8  # word count above which we rewrite


def rewrite_query(message: str, settings: Settings) -> str:
    """Distill a conversational message into focused search keywords."""
    if len(message.split()) <= _REWRITE_THRESHOLD:
        return message
    try:
        messages = [
            {"role": "system", "content": QUERY_REWRITE_PROMPT},
            {"role": "user", "content": message},
        ]
        rewritten = get_completion(messages, settings)
        rewritten = rewritten.strip().strip('"').strip("'")
        if rewritten:
            logger.info("Query rewrite: %r -> %r", message[:80], rewritten)
            return rewritten
    except Exception:
        logger.warning("Query rewrite failed, using original")
    return message


def chat_respond(message: str, retriever: Retriever,
                 settings: Settings, chatdb=None,
                 thread_id: str | None = None) -> Generator:
    """Generate a streaming RAG response for the given message."""
    if not message.strip():
        yield ""
        return

    search_query = rewrite_query(message, settings)
    results = retriever.search(search_query)

    if not results:
        reply = ("I don't have any relevant information in your knowledge base. "
                 "Try indexing some documents first.")
        yield reply
        _persist(chatdb, thread_id, message, reply)
        return

    documents = [r.document for r in results]
    metadatas = [r.metadata for r in results]

    # Load conversation history from thread DB or in-memory fallback
    if thread_id and chatdb:
        db_msgs = chatdb.get_messages(thread_id)
        history = [{"role": m["role"], "content": m["content"]}
                   for m in db_msgs]
        history = history[-(MAX_HISTORY * 2):]
    else:
        history = conversation_history.get_history()

    messages = build_rag_messages(
        message, documents, metadatas,
        conversation_history=history,
        system_prompt=settings.system_prompt,
    )

    raw_response = ""
    cleaned = ""
    last_yielded = ""
    last_check = 0
    try:
        for chunk in get_streaming_completion(messages, settings):
            raw_response += chunk
            # Yield raw (with think blocks) for frontend collapsible UI
            if raw_response != last_yielded:
                yield raw_response
                last_yielded = raw_response

            # Track cleaned version for repetition detection
            cleaned = _strip_thinking(raw_response)
            if len(cleaned) - last_check >= 200:
                last_check = len(cleaned)
                if _is_repeating(cleaned):
                    cleaned = _truncate_at_repeat(cleaned)
                    logger.warning("Repetition detected, truncating")
                    yield cleaned
                    break
    except RuntimeError as e:
        logger.error("LLM error: %s", e)
        error_msg = f"Error communicating with LLM: {e}"
        yield error_msg
        _persist(chatdb, thread_id, message, error_msg)
        return

    # Final clean for storage
    cleaned = _strip_thinking(raw_response)

    sources = extract_unique_sources(metadatas)
    if sources and "Source:" not in cleaned:
        source_block = "\n\n---\n**Sources:**\n" + "\n".join(
            f"- `{s}`" for s in sources
        )
        raw_response += source_block
        yield raw_response

    # Persist messages
    store_text = _strip_source_block(cleaned)
    _persist(chatdb, thread_id, message, store_text)


def save_last_response_as_plan(history: list, settings: Settings) -> str:
    """Save the last assistant response as a markdown plan file."""
    if not history:
        return "No conversation to save."

    last_bot_msg = None
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            last_bot_msg = msg["content"]
            break

    if not last_bot_msg:
        return "No assistant response to save."

    save_dir = Path(settings.plans_save_directory)
    save_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"plan_{timestamp}.md"
    filepath = save_dir / filename

    user_msg = ""
    for msg in reversed(history):
        if msg.get("role") == "user":
            user_msg = msg["content"]
            break

    content = f"# Plan: {user_msg[:80]}\n\n"
    content += f"*Generated: {datetime.now().isoformat()}*\n\n"
    content += last_bot_msg

    filepath.write_text(content, encoding="utf-8")
    return f"Plan saved to: {filepath}"
