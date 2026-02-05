"""File browser and settings UI components."""

import logging
from pathlib import Path

import gradio as gr

from app.config import Settings
from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)


def build_browser_tab(retriever: Retriever) -> gr.Blocks:
    """Build the file browser tab for viewing indexed files."""
    with gr.Blocks() as tab:
        gr.Markdown("## Browse Knowledge Base")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Indexed Files")
                file_list = gr.Dataframe(
                    headers=["File", "Folder"],
                    label="Files",
                    interactive=False,
                )
                refresh_btn = gr.Button("Refresh File List")

            with gr.Column(scale=2):
                gr.Markdown("### File Content")
                selected_file = gr.Textbox(
                    label="Selected File Path",
                    interactive=True,
                    placeholder="Click a file or paste a path",
                )
                file_content = gr.Markdown(label="Content")
                load_btn = gr.Button("Load File")

        def get_file_list():
            sources = retriever.get_unique_sources()
            rows = []
            for s in sources:
                p = Path(s)
                rows.append([p.name, str(p.parent)])
            return rows

        def load_file(filepath: str):
            if not filepath or not filepath.strip():
                return "Select a file to view."
            p = Path(filepath.strip())
            if not p.exists():
                return f"File not found: {filepath}"
            try:
                return p.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                return f"Error reading file: {e}"

        def on_row_select(evt: gr.SelectData, data):
            if evt.index is not None and data is not None:
                row_idx = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
                sources = retriever.get_unique_sources()
                if row_idx < len(sources):
                    path = sources[row_idx]
                    content = load_file(path)
                    return path, content
            return "", ""

        refresh_btn.click(get_file_list, outputs=[file_list])
        load_btn.click(load_file, [selected_file], [file_content])
        file_list.select(on_row_select, [file_list], [selected_file, file_content])
        tab.load(get_file_list, outputs=[file_list])

    return tab


def build_settings_tab(settings: Settings, reindex_fn) -> gr.Blocks:
    """Build the settings tab for LLM config and source management."""
    with gr.Blocks() as tab:
        gr.Markdown("## Settings")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### LLM Configuration")
                provider_dropdown = gr.Dropdown(
                    choices=[p["name"] for p in settings.llm_providers],
                    value=settings.active_provider,
                    label="Active Provider",
                )
                for p in settings.llm_providers:
                    with gr.Accordion(f"Provider: {p['name']}", open=False):
                        gr.Textbox(value=p.get("model", ""), label="Model",
                                   interactive=False)
                        gr.Textbox(value=p.get("api_base", ""), label="API Base",
                                   interactive=False)

                save_provider_btn = gr.Button("Save Provider Selection")
                provider_status = gr.Textbox(label="", interactive=False)

            with gr.Column():
                gr.Markdown("### Source Directories")
                sources_display = gr.Dataframe(
                    headers=["Source Path"],
                    value=[[s] for s in settings.sources],
                    label="Configured Sources",
                    interactive=False,
                )
                new_source = gr.Textbox(
                    label="Add Source Directory",
                    placeholder="/path/to/your/markdown/files",
                )
                add_source_btn = gr.Button("Add Source")
                source_status = gr.Textbox(label="", interactive=False)

        with gr.Row():
            with gr.Column():
                gr.Markdown("### Indexing")
                reindex_btn = gr.Button("Re-index All Sources", variant="primary")
                index_status = gr.Textbox(label="Indexing Status", interactive=False)

            with gr.Column():
                gr.Markdown("### Features")
                for fname, enabled in settings.features.items():
                    gr.Checkbox(value=enabled, label=fname, interactive=False)

        def save_provider(provider_name):
            settings.active_provider = provider_name
            settings.save()
            return f"Active provider set to: {provider_name}"

        def add_source(path):
            if not path.strip():
                return [[s] for s in settings.sources], "Enter a path first."
            settings.add_source(path.strip())
            settings.save()
            return [[s] for s in settings.sources], f"Added: {path.strip()}"

        def do_reindex():
            try:
                return reindex_fn()
            except RuntimeError as e:
                return f"Error during reindex: {e}"

        save_provider_btn.click(save_provider, [provider_dropdown], [provider_status])
        add_source_btn.click(add_source, [new_source], [sources_display, source_status])
        reindex_btn.click(do_reindex, outputs=[index_status])

    return tab
