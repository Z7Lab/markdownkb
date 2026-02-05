"""File browser and settings UI components."""

import logging
from pathlib import Path

import gradio as gr
import litellm
import requests

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
            """Return indexed files as rows."""
            sources = retriever.get_unique_sources()
            return [
                [Path(s).name, str(Path(s).parent)]
                for s in sources
            ]

        def load_file(filepath: str):
            """Load and return file contents."""
            if not filepath or not filepath.strip():
                return "Select a file to view."
            p = Path(filepath.strip())
            if not p.exists():
                return f"File not found: {filepath}"
            try:
                return p.read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError as e:
                return f"Error reading file: {e}"

        def on_row_select(evt: gr.SelectData, data):
            """Handle file list row selection."""
            if evt.index is not None and data is not None:
                row_idx = (
                    evt.index[0]
                    if isinstance(evt.index, (list, tuple))
                    else evt.index
                )
                sources = retriever.get_unique_sources()
                if row_idx < len(sources):
                    path = sources[row_idx]
                    content = load_file(path)
                    return path, content
            return "", ""

        refresh_btn.click(get_file_list, outputs=[file_list])
        load_btn.click(
            load_file, [selected_file], [file_content]
        )
        file_list.select(
            on_row_select,
            [file_list],
            [selected_file, file_content],
        )
        tab.load(get_file_list, outputs=[file_list])

    return tab


def _fetch_ollama_models(api_base):
    """Fetch available models from an Ollama instance."""
    try:
        resp = requests.get(
            f"{api_base.rstrip('/')}/api/tags", timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return [
                m["name"] for m in data.get("models", [])
            ]
    except requests.RequestException:
        pass
    return []


def _get_provider_values(settings, name):
    """Look up a provider's model and api_base by name."""
    for p in settings.llm_providers:
        if p.get("name") == name:
            return p.get("model", ""), p.get("api_base", "")
    return "", ""


def _test_ollama(api_base):
    """Test connectivity to an Ollama instance."""
    try:
        resp = requests.get(
            f"{api_base.rstrip('/')}/api/tags", timeout=10,
        )
    except requests.ConnectionError:
        return f"Cannot reach {api_base} - is Ollama running?"
    except requests.RequestException as e:
        return f"Connection error: {e}"

    if resp.status_code != 200:
        return f"Connection failed: HTTP {resp.status_code}"

    data = resp.json()
    models = [m["name"] for m in data.get("models", [])]
    if models:
        return (
            f"Connected to {api_base}\n"
            f"Available models: {', '.join(models)}"
        )
    return (
        f"Connected to {api_base} but no models found. "
        "Pull a model first."
    )


def _test_api_provider(model, api_base):
    """Test connectivity to an API-based LLM provider."""
    litellm.drop_params = True
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": "Say OK"}],
        "max_tokens": 5,
        "temperature": 0,
    }
    if api_base:
        kwargs["api_base"] = api_base

    try:
        response = litellm.completion(**kwargs)
        reply = response.choices[0].message.content or ""
        return f"Connected. Response: {reply.strip()}"
    except (
        litellm.APIError, litellm.APIConnectionError,
        litellm.Timeout, litellm.AuthenticationError,
        RuntimeError, OSError, ValueError,
    ) as e:
        return f"Connection failed: {e}"


def _test_llm_connection(provider_name, model, api_base):
    """Test connectivity to an LLM provider."""
    if not model:
        return "No model configured."

    if "ollama" in provider_name.lower() and api_base:
        return _test_ollama(api_base)

    return _test_api_provider(model, api_base)


def _build_sources_column(settings):
    """Build the source directories column with add functionality."""
    gr.Markdown("### Source Directories")
    sources_display = gr.Dataframe(
        headers=["Source Path"],
        value=[[s] for s in settings.sources],
        label="Configured Sources",
        interactive=False,
    )
    new_source = gr.Textbox(
        label="Add Source Directory",
        placeholder="/path/to/markdown/files",
    )
    add_source_btn = gr.Button("Add Source")
    source_status = gr.Textbox(label="", interactive=False)

    def add_source(path):
        """Add a new source directory."""
        if not path.strip():
            return (
                [[s] for s in settings.sources],
                "Enter a path first.",
            )
        settings.add_source(path.strip())
        settings.save()
        return (
            [[s] for s in settings.sources],
            f"Added: {path.strip()}",
        )

    add_source_btn.click(
        add_source,
        [new_source],
        [sources_display, source_status],
    )


def _build_index_features_row(settings, reindex_fn):
    """Build the indexing and features row."""
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Indexing")
            reindex_btn = gr.Button(
                "Re-index All Sources", variant="primary"
            )
            index_status = gr.Textbox(
                label="Indexing Status", interactive=False,
            )

        with gr.Column():
            gr.Markdown("### Features")
            for fname, enabled in settings.features.items():
                gr.Checkbox(
                    value=enabled, label=fname,
                    interactive=False,
                )

    def do_reindex():
        """Trigger a full re-index."""
        try:
            return reindex_fn()
        except RuntimeError as e:
            return f"Error during reindex: {e}"

    reindex_btn.click(do_reindex, outputs=[index_status])


def _initial_model_choices(settings):
    """Build the initial model dropdown choices for the active provider."""
    cfg = settings.get_active_llm_config()
    current_model = cfg.get("model", "")
    api_base = cfg.get("api_base", "")
    name = cfg.get("name", "")

    choices = []
    # For Ollama, try to fetch models on startup
    if "ollama" in name.lower() and api_base:
        raw_models = _fetch_ollama_models(api_base)
        choices = [f"ollama/{m}" for m in raw_models]

    # Make sure current model is in the list
    if current_model and current_model not in choices:
        choices.insert(0, current_model)

    return choices if choices else [current_model]


def build_settings_tab(
    settings: Settings, reindex_fn
) -> gr.Blocks:
    """Build the settings tab for LLM config and sources."""
    active_cfg = settings.get_active_llm_config()
    initial_choices = _initial_model_choices(settings)

    with gr.Blocks() as tab:
        gr.Markdown("## Settings")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### LLM Configuration")
                provider_dropdown = gr.Dropdown(
                    choices=[
                        p["name"]
                        for p in settings.llm_providers
                    ],
                    value=settings.active_provider,
                    label="Active Provider",
                )
                api_base_input = gr.Textbox(
                    value=active_cfg.get("api_base", ""),
                    label="API Base",
                    placeholder="Leave empty for default",
                )
                with gr.Row():
                    model_dropdown = gr.Dropdown(
                        choices=initial_choices,
                        value=active_cfg.get("model", ""),
                        label="Model",
                        allow_custom_value=True,
                        scale=5,
                    )
                    refresh_models_btn = gr.Button(
                        "Refresh Models", scale=1,
                    )

                with gr.Row():
                    save_btn = gr.Button(
                        "Save Provider Settings"
                    )
                    test_btn = gr.Button(
                        "Test Connection",
                        variant="secondary",
                    )
                status_box = gr.Textbox(
                    label="Status",
                    interactive=False,
                    lines=3,
                )

            with gr.Column():
                _build_sources_column(settings)

        _build_index_features_row(settings, reindex_fn)

        def on_provider_change(provider_name):
            """Load the selected provider's settings."""
            model, api_base = _get_provider_values(
                settings, provider_name
            )
            # Build model choices for this provider
            choices = _build_model_choices(
                provider_name, api_base, model
            )
            return (
                api_base,
                gr.update(
                    choices=choices, value=model,
                ),
            )

        def refresh_models(provider_name, api_base):
            """Fetch models from the provider and update dropdown."""
            choices, status = _build_model_list(
                provider_name, api_base
            )
            if not choices:
                return gr.update(), status
            return (
                gr.update(choices=choices, value=choices[0]),
                status,
            )

        def save_provider(name, model, api_base):
            """Save provider selection and config."""
            settings.active_provider = name
            for p in settings.llm_providers:
                if p.get("name") == name:
                    p["model"] = model
                    p["api_base"] = api_base
                    break
            settings.save()
            return (
                f"Saved: {name}\n"
                f"Model: {model}\n"
                f"API Base: {api_base or '(default)'}"
            )

        def test_connection(name, model, api_base):
            """Test the LLM provider connection."""
            return _test_llm_connection(name, model, api_base)

        provider_dropdown.change(
            on_provider_change,
            [provider_dropdown],
            [api_base_input, model_dropdown],
        )
        refresh_models_btn.click(
            refresh_models,
            [provider_dropdown, api_base_input],
            [model_dropdown, status_box],
        )
        save_btn.click(
            save_provider,
            [provider_dropdown, model_dropdown,
             api_base_input],
            [status_box],
        )
        test_btn.click(
            test_connection,
            [provider_dropdown, model_dropdown,
             api_base_input],
            [status_box],
        )

    return tab


def _build_model_choices(provider_name, api_base, current):
    """Build model dropdown choices for a provider."""
    choices = []
    if "ollama" in provider_name.lower() and api_base:
        raw = _fetch_ollama_models(api_base)
        choices = [f"ollama/{m}" for m in raw]
    if current and current not in choices:
        choices.insert(0, current)
    return choices if choices else [current] if current else []


def _build_model_list(provider_name, api_base):
    """Fetch and return model list with status message."""
    if "ollama" in provider_name.lower() and api_base:
        raw = _fetch_ollama_models(api_base)
        if raw:
            choices = [f"ollama/{m}" for m in raw]
            return choices, f"Found {len(raw)} model(s)"
        return [], f"No models found at {api_base}"
    return [], "Refresh only works for Ollama providers"
