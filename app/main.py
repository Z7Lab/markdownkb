import logging
import threading

import gradio as gr

from app.config import Settings
from app.embeddings.embedder import embed_texts
from app.ingestion.parser import parse_and_chunk
from app.ingestion.scanner import scan_sources
from app.rag.retriever import Retriever
from app.storage.vectorstore import VectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def do_index(settings: Settings, store: VectorStore) -> str:
    logger.info("Starting indexing...")
    files = scan_sources(settings.sources, settings.global_ignore)
    logger.info(f"Found {len(files)} markdown files")

    all_chunks = []
    for fi in files:
        chunks = parse_and_chunk(
            fi.path, fi.source_root,
            settings.chunk_size, settings.chunk_overlap,
        )
        all_chunks.extend(chunks)

    if not all_chunks:
        return "No markdown files found to index."

    logger.info(f"Embedding {len(all_chunks)} chunks...")
    texts = [c.content for c in all_chunks]
    embeddings = embed_texts(texts, settings.embedding_model)

    ids = [c.chunk_id for c in all_chunks]
    metadatas = [c.metadata for c in all_chunks]

    store.add(ids, texts, embeddings, metadatas)
    msg = f"Indexed {len(files)} files, {len(all_chunks)} chunks. Store total: {store.count}"
    logger.info(msg)
    return msg


def build_app(settings: Settings) -> gr.Blocks:
    store = VectorStore(settings.persist_directory, settings.collection_name)
    retriever = Retriever(store, settings)

    def reindex_fn():
        return do_index(settings, store)

    # Import UI builders
    from app.ui.chat import build_chat_tab
    from app.ui.browser import build_browser_tab, build_settings_tab

    with gr.Blocks(
        title="mdkb - Markdown Knowledge Base",
        theme=gr.themes.Soft(),
    ) as app:
        gr.Markdown("# mdkb — Markdown Knowledge Base")
        gr.Markdown("*Your personal dev assistant with long-term memory*")

        with gr.Tabs():
            with gr.Tab("Chat"):
                build_chat_tab(retriever, settings)

            with gr.Tab("Search"):
                _build_search_tab(retriever, settings)

            with gr.Tab("Browse"):
                build_browser_tab(retriever, settings)

            with gr.Tab("Settings"):
                build_settings_tab(settings, reindex_fn)

    # Start file watcher if enabled
    if settings.feature_enabled("file_watcher"):
        _start_watcher(settings, store)

    return app


def _build_search_tab(retriever: Retriever, settings: Settings) -> gr.Blocks:
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
            search_btn = gr.Button("Search", variant="primary", scale=1)

        results_display = gr.Markdown(label="Results")

        def do_search(query, folder, tag):
            if not query.strip():
                return "Enter a search query."

            f = None if folder == "(all)" else folder
            t = None if tag == "(all)" else tag
            results = retriever.search(query.strip(), folder_filter=f, tag_filter=t)

            if not results:
                return "No results found."

            output = ""
            for i, r in enumerate(results):
                source = r.metadata.get("source_path", "unknown")
                heading = r.metadata.get("heading", "")
                output += f"### Result {i+1} (score: {r.score:.3f})\n"
                output += f"**Source:** `{source}`"
                if heading:
                    output += f" | **Section:** {heading}"
                output += f"\n\n{r.document[:500]}{'...' if len(r.document) > 500 else ''}\n\n---\n\n"
            return output

        def refresh_filters():
            folders = ["(all)"] + retriever.get_unique_folders()
            tags = ["(all)"] + retriever.get_unique_tags()
            return (
                gr.update(choices=folders, value="(all)"),
                gr.update(choices=tags, value="(all)"),
            )

        search_btn.click(do_search, [query_input, folder_filter, tag_filter],
                         [results_display])
        query_input.submit(do_search, [query_input, folder_filter, tag_filter],
                           [results_display])
        tab.load(refresh_filters, outputs=[folder_filter, tag_filter])

    return tab


def _start_watcher(settings: Settings, store: VectorStore):
    try:
        from app.ingestion.watcher import start_watching
        thread = threading.Thread(
            target=start_watching,
            args=(settings, store),
            daemon=True,
        )
        thread.start()
        logger.info("File watcher started")
    except Exception as e:
        logger.warning(f"Failed to start file watcher: {e}")


def main():
    settings = Settings.get()

    # Auto-index on startup if store is empty
    store = VectorStore(settings.persist_directory, settings.collection_name)
    if store.count == 0:
        logger.info("Empty store, running initial index...")
        do_index(settings, store)

    app = build_app(settings)

    # Mount FastAPI alongside Gradio
    from app.api import create_api
    retriever = Retriever(store, settings)
    fastapi_app = create_api(settings, store, retriever)
    gr.mount_gradio_app(fastapi_app, app, path="/")

    import uvicorn
    uvicorn.run(
        fastapi_app,
        host=settings.server_host,
        port=settings.server_port,
    )


if __name__ == "__main__":
    main()
