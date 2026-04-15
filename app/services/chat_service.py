"""Chat business logic: conversation memory, streaming RAG, plan saving."""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generator

from fastapi import HTTPException

from app.config import Settings
from app.rag.llm import get_completion, get_streaming_completion, strip_thinking
from app.rag.prompts import build_rag_messages, get_query_rewrite_prompt
from app.rag.retriever import Retriever


@dataclass
class ChatScope:
    """Resolved scope + bucket context for a chat turn.

    Computed once by ``resolve_chat_scope`` so the route handler doesn't have
    to know about scope resolution, tag expansion, or bucket lookup.
    """

    scope_folders: list[str] | None
    allowed_paths: set[str] | None
    exclude_patterns: list
    bucket_retrievers: list
    bucket_only: bool

    @property
    def has_scope(self) -> bool:
        return bool(self.scope_folders or self.allowed_paths)


def resolve_chat_scope(
    *,
    app_state,
    scope_ids: list[str] | None,
    scope_id: str | None,
    bucket_ids: list[str] | None,
    ad_hoc_tags: list[str] | None,
    settings: Settings,
    scopedb,
) -> ChatScope:
    """Resolve scopes/tags/buckets into a single ``ChatScope`` bundle.

    Extracted from ``chat_stream`` so the orchestration is reusable (and
    testable) in isolation. Raises ``HTTPException`` on unknown buckets or a
    missing buckets plugin, matching the previous inline behavior.
    """
    from app.scope_utils import parse_scope_ids, resolve_scopes
    from app.tag_utils import resolve_tag_paths

    ids = parse_scope_ids(scope_ids) or ([scope_id] if scope_id else None)
    scope_folders, scope_tags, exclude_patterns = resolve_scopes(ids, scopedb)
    allowed = resolve_tag_paths(scope_tags, ad_hoc_tags)

    bucket_retrievers: list = []
    b_ids = parse_scope_ids(bucket_ids)
    if b_ids:
        bucket_service = getattr(app_state, "bucket_service", None)
        if bucket_service is None:
            raise HTTPException(status_code=503, detail="Buckets plugin not initialized")
        for bid in b_ids:
            record = bucket_service.db.resolve(bid)
            if not record:
                raise HTTPException(status_code=404, detail=f"Bucket not found: {bid}")
            bucket_retrievers.append(bucket_service.get_retriever(record["id"], settings))

    has_scope = bool(scope_folders or allowed)
    return ChatScope(
        scope_folders=scope_folders,
        allowed_paths=allowed,
        exclude_patterns=exclude_patterns,
        bucket_retrievers=bucket_retrievers,
        bucket_only=bool(bucket_retrievers) and not has_scope,
    )

logger = logging.getLogger(__name__)

MAX_HISTORY = 20
REPEAT_WINDOW = 150


class ConversationHistory:
    """Thread-safe in-memory conversation memory (fallback for non-threaded chat).

    Prefer ChatDB thread-based storage.  This is only used when no
    ``thread_id`` is provided and exists as a lightweight fallback.
    It is stored on ``app.state.conversation_history`` so its lifetime
    is tied to the application instance — not the module.
    """

    def __init__(self):
        self._history: list[dict] = []
        self._lock = threading.Lock()

    def add(self, role: str, content: str):
        """Append a message and trim if over limit."""
        with self._lock:
            self._history.append({"role": role, "content": content})
            if len(self._history) > MAX_HISTORY * 2:
                self._history = self._history[-(MAX_HISTORY * 2):]

    def get_history(self) -> list[dict]:
        """Return the recent conversation history."""
        with self._lock:
            return list(self._history[-(MAX_HISTORY * 2):])

    def clear(self):
        """Clear all conversation history."""
        with self._lock:
            self._history = []


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


def _persist(chatdb, thread_id: str | None, user_msg: str, assistant_msg: str,
             conversation_history: ConversationHistory | None = None,
             settings: Settings | None = None):
    """Save user + assistant messages to the thread DB."""
    provider = None
    model = None
    if settings:
        provider = settings.active_provider
        active_cfg = settings.get_active_llm_config()
        model = active_cfg.get("model", "")
    if thread_id and chatdb:
        chatdb.add_message(thread_id, "user", user_msg)
        chatdb.add_message(thread_id, "assistant", assistant_msg,
                           provider=provider, model=model)
    elif conversation_history is not None:
        conversation_history.add("user", user_msg)
        conversation_history.add("assistant", assistant_msg)
    else:
        logger.debug("No chatdb or conversation_history — messages not persisted")


_REWRITE_THRESHOLD = 8  # word count above which we rewrite


def rewrite_query(message: str, settings: Settings) -> str:
    """Distill a conversational message into focused search keywords."""
    if len(message.split()) <= _REWRITE_THRESHOLD:
        return message
    try:
        messages = [
            {"role": "system", "content": get_query_rewrite_prompt()},
            {"role": "user", "content": message},
        ]
        rewritten = get_completion(messages, settings)
        rewritten = strip_thinking(rewritten)
        rewritten = rewritten.strip().strip('"').strip("'")
        if rewritten:
            logger.info("Query rewrite: %r -> %r", message[:80], rewritten)
            return rewritten
    except (RuntimeError, OSError, ValueError) as e:
        logger.warning("Query rewrite failed, using original: %s", e)
    return message


def chat_respond(message: str, retriever: Retriever,
                 settings: Settings, chatdb=None,
                 thread_id: str | None = None,
                 folders_filter: list[str] | None = None,
                 scope_tags: list[str] | None = None,
                 allowed_paths: set[str] | None = None,
                 exclude_patterns: list[str] | None = None,
                 bucket_retrievers: list[Retriever] | None = None,
                 sources_out: list[str] | None = None,
                 source_map_out: dict[str, str] | None = None,
                 conversation_history: ConversationHistory | None = None,
                 history_override: list[dict] | None = None) -> Generator:
    """Generate a streaming RAG response for the given message.

    When ``bucket_retrievers`` is provided alongside the main retriever,
    all bucket stores are searched and results are merged — enabling combined
    scope + bucket queries. Multiple buckets are also supported.
    """
    if not message.strip():
        yield ""
        return

    search_query = rewrite_query(message, settings)
    results = retriever.search(
        search_query, folders_filter=folders_filter, scope_tags=scope_tags,
        allowed_paths=allowed_paths, exclude_patterns=exclude_patterns,
    )

    # Merge bucket results when both scope and bucket(s) are active
    if bucket_retrievers:
        for br in bucket_retrievers:
            bucket_results = br.search(search_query)
            for r in bucket_results:
                r.metadata["_bucket"] = "true"
            results = results + bucket_results
        results = sorted(results, key=lambda r: r.score, reverse=True)[:settings.top_k]

    if not results:
        reply = ("I don't have any relevant information in your knowledge base. "
                 "Try indexing some documents first.")
        yield reply
        _persist(chatdb, thread_id, message, reply, conversation_history, settings)
        return

    documents = [r.document for r in results]
    metadatas = [r.metadata for r in results]

    # Load conversation history: thread DB → explicit override → in-memory fallback
    if thread_id and chatdb:
        db_msgs = chatdb.get_messages(thread_id)
        history = [{"role": m["role"], "content": m["content"]}
                   for m in db_msgs]
        history = history[-(MAX_HISTORY * 2):]
    elif history_override is not None:
        history = history_override[-(MAX_HISTORY * 2):]
    else:
        history = conversation_history.get_history() if conversation_history else []

    messages, source_map = build_rag_messages(
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
            cleaned = strip_thinking(raw_response)
            if len(cleaned) - last_check >= 200:
                last_check = len(cleaned)
                if _is_repeating(cleaned):
                    cleaned = _truncate_at_repeat(cleaned)
                    logger.warning("Repetition detected, truncating")
                    yield cleaned
                    break
    except RuntimeError as e:
        logger.error("LLM error: %s", e)
        raise

    # Final clean for storage
    cleaned = strip_thinking(raw_response)

    sources = extract_unique_sources(metadatas)
    if sources_out is not None:
        sources_out.extend(sources)
    if source_map_out is not None:
        source_map_out.update(source_map)

    # Persist messages
    store_text = _strip_source_block(cleaned)
    _persist(chatdb, thread_id, message, store_text, conversation_history, settings)


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
