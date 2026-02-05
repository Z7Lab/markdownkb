"""Chat interface with streaming responses and conversation memory."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Generator

import gradio as gr

from app.config import Settings
from app.rag.llm import get_streaming_completion
from app.rag.prompts import build_rag_messages
from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)

MAX_HISTORY = 20


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


def chat_respond(message: str, retriever: Retriever,
                 settings: Settings) -> Generator:
    """Generate a streaming RAG response for the given message."""
    if not message.strip():
        yield ""
        return

    results = retriever.search(message)

    if not results:
        yield ("I don't have any relevant information in your knowledge base. "
               "Try indexing some documents first.")
        return

    documents = [r.document for r in results]
    metadatas = [r.metadata for r in results]

    messages = build_rag_messages(
        message, documents, metadatas,
        conversation_history=conversation_history.get_history(),
    )

    full_response = ""
    try:
        for chunk in get_streaming_completion(messages, settings):
            full_response += chunk
            yield full_response
    except RuntimeError as e:
        logger.error("LLM error: %s", e)
        yield f"Error communicating with LLM: {e}"
        return

    sources = _extract_unique_sources(metadatas)
    if sources and "Source:" not in full_response:
        source_block = "\n\n---\n**Sources:**\n" + "\n".join(
            f"- `{s}`" for s in sources
        )
        full_response += source_block
        yield full_response

    conversation_history.add("user", message)
    conversation_history.add("assistant", full_response)


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


def _extract_unique_sources(metadatas: list[dict]) -> list[str]:
    """Extract deduplicated source file paths from metadata list."""
    seen = set()
    sources = []
    for m in metadatas:
        src = m.get("source_path", "")
        if src and src not in seen:
            seen.add(src)
            sources.append(src)
    return sources


def build_chat_tab(retriever: Retriever, settings: Settings) -> gr.Blocks:
    """Build the Gradio chat tab with send, clear, and save controls."""
    with gr.Blocks() as tab:
        chatbot = gr.Chatbot(
            label="mdkb Chat",
            height=500,
        )
        with gr.Row():
            msg = gr.Textbox(
                label="Ask your knowledge base",
                placeholder="What did I write about...?",
                scale=8,
                lines=1,
            )
            send_btn = gr.Button("Send", variant="primary", scale=1)

        with gr.Row():
            clear_btn = gr.Button("Clear Chat")
            save_btn = gr.Button("Save Last Response as Plan")
            save_status = gr.Textbox(label="", interactive=False, scale=2)

        def respond(message, history):
            history = history or []
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": ""})
            for partial in chat_respond(message, retriever, settings):
                history[-1]["content"] = partial
                yield history, ""
            yield history, ""

        def clear():
            conversation_history.clear()
            return [], ""

        def save_plan(history):
            return save_last_response_as_plan(history, settings)

        msg.submit(respond, [msg, chatbot], [chatbot, msg])
        send_btn.click(respond, [msg, chatbot], [chatbot, msg])
        clear_btn.click(clear, outputs=[chatbot, msg])
        save_btn.click(save_plan, [chatbot], [save_status])

    return tab
