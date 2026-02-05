"""Main application entry point - Gradio UI with FastAPI backend."""

import logging
import threading

import gradio as gr
import uvicorn

from app.api import create_api
from app.config import Settings
from app.ingestion.indexer import run_index
from app.rag.retriever import Retriever
from app.storage.vectorstore import VectorStore
from app.ui.browser import build_browser_tab, build_settings_tab
from app.ui.chat import build_chat_tab

try:
    from app.ingestion.watcher import start_watching
    _HAS_WATCHER = True
except ImportError:
    _HAS_WATCHER = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def build_app(settings: Settings) -> gr.Blocks:
    """Build the Gradio application with all tabs."""
    store = VectorStore(
        settings.persist_directory, settings.collection_name
    )
    retriever = Retriever(store, settings)

    def reindex_fn(progress=None):
        return run_index(settings, store, progress=progress)

    with gr.Blocks(title="mdkb - Markdown Knowledge Base") as app:
        gr.Markdown("# mdkb - Markdown Knowledge Base")
        gr.Markdown(
            "*Your personal dev assistant with long-term memory*"
        )

        with gr.Tabs():
            with gr.Tab("Chat"):
                build_chat_tab(retriever, settings)

            with gr.Tab("Search"):
                _build_search_tab(retriever)

            with gr.Tab("Browse"):
                build_browser_tab(retriever)

            with gr.Tab("Settings"):
                build_settings_tab(settings, reindex_fn)

    if settings.feature_enabled("file_watcher"):
        _start_watcher(settings, store)

    return app


def _build_search_tab(retriever: Retriever) -> gr.Blocks:
    """Build the semantic search tab with folder/tag filtering."""
    with gr.Blocks() as tab:
        gr.Markdown("## Semantic Search")
        with gr.Row():
            query_input = gr.Textbox(
                label="Search Query",
                placeholder="Search your knowledge base...",
                scale=6,
            )
            folder_filter = gr.Dropdown(
                label="Filter by folder",
                choices=["(all)"],
                value="(all)",
                scale=2,
            )
            tag_filter = gr.Dropdown(
                label="Filter by tag",
                choices=["(all)"],
                value="(all)",
                scale=2,
            )
            search_btn = gr.Button(
                "Search", variant="primary", scale=1
            )

        results_display = gr.Markdown(label="Results")

        def do_search(query, folder, tag):
            if not query.strip():
                return "Enter a search query."

            f_val = None if folder == "(all)" else folder
            t_val = None if tag == "(all)" else tag
            results = retriever.search(
                query.strip(),
                folder_filter=f_val,
                tag_filter=t_val,
            )

            if not results:
                return "No results found."

            output = ""
            for i, r in enumerate(results):
                source = r.metadata.get("source_path", "unknown")
                heading = r.metadata.get("heading", "")
                output += (
                    f"### Result {i+1} "
                    f"(score: {r.score:.3f})\n"
                )
                output += f"**Source:** `{source}`"
                if heading:
                    output += f" | **Section:** {heading}"
                truncated = r.document[:500]
                ellipsis = "..." if len(r.document) > 500 else ""
                output += (
                    f"\n\n{truncated}{ellipsis}\n\n---\n\n"
                )
            return output

        def refresh_filters():
            folders = ["(all)"] + retriever.get_unique_folders()
            tags = ["(all)"] + retriever.get_unique_tags()
            return (
                gr.update(choices=folders, value="(all)"),
                gr.update(choices=tags, value="(all)"),
            )

        search_btn.click(
            do_search,
            [query_input, folder_filter, tag_filter],
            [results_display],
        )
        query_input.submit(
            do_search,
            [query_input, folder_filter, tag_filter],
            [results_display],
        )
        tab.load(
            refresh_filters,
            outputs=[folder_filter, tag_filter],
        )

    return tab


def _start_watcher(settings: Settings, store: VectorStore):
    """Start the file watcher daemon thread."""
    if not _HAS_WATCHER:
        logger.warning(
            "watchdog not installed, file watcher disabled"
        )
        return

    thread = threading.Thread(
        target=start_watching,
        args=(settings, store),
        daemon=True,
    )
    thread.start()
    logger.info("File watcher started")


def main():
    """Start the mdkb server with Gradio UI and FastAPI."""
    settings = Settings.get()

    store = VectorStore(
        settings.persist_directory, settings.collection_name
    )
    if store.count == 0:
        logger.info("Empty store, running initial index...")
        run_index(settings, store)

    app = build_app(settings)

    retriever = Retriever(store, settings)
    fastapi_app = create_api(settings, store, retriever)
    gr.mount_gradio_app(fastapi_app, app, path="/")

    uvicorn.run(
        fastapi_app,
        host=settings.server_host,
        port=settings.server_port,
    )


if __name__ == "__main__":
    main()
