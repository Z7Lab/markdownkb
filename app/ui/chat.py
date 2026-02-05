import logging
from datetime import datetime
from pathlib import Path
from typing import Generator

import gradio as gr

from app.config import Settings
from app.rag.llm import get_streaming_completion
from app.rag.prompts import build_rag_messages, format_context
from app.rag.retriever import Retriever, SearchResult

logger = logging.getLogger(__name__)

# Conversation memory: list of {"role": ..., "content": ...}
_conversation_history: list[dict] = []
MAX_HISTORY = 20  # Keep last N exchanges


def _trim_history():
    global _conversation_history
    if len(_conversation_history) > MAX_HISTORY * 2:
        _conversation_history = _conversation_history[-(MAX_HISTORY * 2):]


def chat_respond(message: str, history: list, retriever: Retriever,
                 settings: Settings) -> Generator:
    global _conversation_history

    if not message.strip():
        yield ""
        return

    # Retrieve relevant context
    results = retriever.search(message)

    if not results:
        yield ("I don't have any relevant information in your knowledge base. "
               "Try indexing some documents first.")
        return

    documents = [r.document for r in results]
    metadatas = [r.metadata for r in results]

    messages = build_rag_messages(
        message, documents, metadatas,
        conversation_history=_conversation_history[-MAX_HISTORY * 2:],
    )

    # Stream response
    full_response = ""
    try:
        for chunk in get_streaming_completion(messages, settings):
            full_response += chunk
            yield full_response
    except Exception as e:
        logger.error(f"LLM error: {e}")
        yield f"Error communicating with LLM: {e}"
        return

    # Add source citations if not already present
    sources = _extract_unique_sources(metadatas)
    if sources and "Source:" not in full_response:
        source_block = "\n\n---\n**Sources:**\n" + "\n".join(
            f"- `{s}`" for s in sources
        )
        full_response += source_block
        yield full_response

    # Update conversation memory
    _conversation_history.append({"role": "user", "content": message})
    _conversation_history.append({"role": "assistant", "content": full_response})
    _trim_history()


def clear_history():
    global _conversation_history
    _conversation_history = []


def save_last_response_as_plan(history: list, settings: Settings) -> str:
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

    # Get the user's question that prompted this response
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
    seen = set()
    sources = []
    for m in metadatas:
        src = m.get("source_path", "")
        if src and src not in seen:
            seen.add(src)
            sources.append(src)
    return sources


def build_chat_tab(retriever: Retriever, settings: Settings) -> gr.Blocks:
    with gr.Blocks() as tab:
        chatbot = gr.Chatbot(
            label="mdkb Chat",
            height=500,
            type="messages",
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
            for partial in chat_respond(message, history, retriever, settings):
                history[-1]["content"] = partial
                yield history, ""
            yield history, ""

        def clear():
            clear_history()
            return [], ""

        def save_plan(history):
            return save_last_response_as_plan(history, settings)

        msg.submit(respond, [msg, chatbot], [chatbot, msg])
        send_btn.click(respond, [msg, chatbot], [chatbot, msg])
        clear_btn.click(clear, outputs=[chatbot, msg])
        save_btn.click(save_plan, [chatbot], [save_status])

    return tab
