# Embedding Models

mdkb uses ONNX-based embedding models for semantic search. All models run locally on CPU — no GPU or external API required.

## Auto-Download

On first startup, mdkb automatically downloads the configured embedding model from HuggingFace. You'll see download progress in the logs:

```
Embedding model 'all-MiniLM-L6-v2' not found, downloading...
  onnx/model.onnx: 45.2 MB / 90.4 MB (50%)
  onnx/model.onnx: 90.4 MB / 90.4 MB (100%)
  tokenizer.json: 711.2 KB downloaded
Embedding model 'all-MiniLM-L6-v2' installed
```

No manual install step is needed. You can also install additional models from the Settings UI.

## Built-in Models

These ship in the default `settings.yaml`:

| Model | Dimensions | Max Tokens | Size | Notes |
|-------|-----------|------------|------|-------|
| all-MiniLM-L6-v2 | 384 | 256 | ~23 MB | Default. Fast, good general quality. |
| all-MiniLM-L12-v2 | 384 | 256 | ~33 MB | Better quality, same dimensions as L6. Slightly slower. |
| bge-small-en-v1.5 | 384 | 512 | ~33 MB | Best retrieval quality. Longer context window. |

All three models output 384-dimensional vectors, so switching between them doesn't require schema changes — just a full reindex.

## Switching Models

From the **Settings** tab in the UI:

1. Find the **Embedding Model** panel
2. If the model you want shows "Not installed", click **Install** (downloads from HuggingFace or copies from local path)
3. Click **Use** on an installed model
4. Confirm the reindex warning — switching clears all indexed data and reindexes every document
5. Progress updates appear in the status area while reindexing runs in the background

You can continue using the app while reindexing. The cancel button in the Index panel will stop a running reindex.

## Adding Custom Models

All models are defined in `config/settings.yaml` under `embeddings.models`. You can add any ONNX sentence-transformer model from HuggingFace.

### From HuggingFace

Add an entry to the models list:

```yaml
embeddings:
  model: all-MiniLM-L6-v2  # active model
  models:
  # ... existing models ...
  - model_id: my-custom-model
    display_name: My Custom Model
    huggingface_repo: username/my-onnx-model
    dimensions: 768
    max_seq_length: 512
    description: 'My fine-tuned embedding model'
```

Required fields:

| Field | Description |
|-------|-------------|
| `model_id` | Unique identifier (used in config and file paths) |
| `display_name` | Human-readable name shown in the UI |
| `huggingface_repo` | HuggingFace repository (e.g. `sentence-transformers/all-MiniLM-L6-v2`) |
| `dimensions` | Output vector dimensions (must match the model) |
| `max_seq_length` | Maximum input token length |

Optional fields:

| Field | Default | Description |
|-------|---------|-------------|
| `description` | `""` | Shown in the UI model list |
| `query_prefix` | `""` | Text prepended to queries (some models like BGE need this) |
| `onnx_path` | `onnx/model.onnx` | Path to the ONNX file within the model directory |
| `tokenizer_path` | `tokenizer.json` | Path to the tokenizer file |
| `files` | see below | List of files to download from HuggingFace |
| `local_path` | `""` | Local directory to copy model from (skips network download) |

Default files downloaded from HuggingFace:
```
onnx/model.onnx, tokenizer.json, tokenizer_config.json,
special_tokens_map.json, config.json, vocab.txt
```

### From a Local Directory

If you have a model already downloaded or on an air-gapped system, point `local_path` at the directory containing the model files:

```yaml
embeddings:
  models:
  - model_id: my-local-model
    display_name: My Local Model
    huggingface_repo: username/model-name
    dimensions: 384
    max_seq_length: 256
    local_path: /path/to/model/directory
```

The directory must contain all required files (by default: `onnx/model.onnx`, `tokenizer.json`, etc.). Files are copied into `data/models/` on install — the original directory is not modified.

This is useful for:
- Air-gapped / offline deployments
- Pre-downloaded models shared across machines
- Custom fine-tuned models not on HuggingFace

## CPU Usage

Embedding and indexing are CPU-bound operations. mdkb limits resource usage by:

- Setting ONNX inference threads to half your CPU cores (`intra_op_num_threads`, `inter_op_num_threads`)
- Throttling the indexing loop with a small sleep between files
- Setting `OMP_NUM_THREADS` to prevent OpenMP from spawning too many threads

For large collections (1000+ files), expect reindexing to take a few minutes.

## Storage

Models are cached locally:

- **Primary:** `data/models/{model-id}/` (inside project root — works with Docker and local dev)
- **Legacy fallback:** `~/.cache/mdkb/models/{model-id}/` (pre-Docker installs, checked automatically)
- **ChromaDB built-in L6:** `~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/` (detected automatically if present)

The active model is stored in `config/settings.yaml` under `embeddings.model`.

## Config

In `config/settings.yaml`:

```yaml
embeddings:
  model: all-MiniLM-L6-v2   # or any model_id from the models list
  chunk_size: 512
  chunk_overlap: 50
  models:
  - model_id: all-MiniLM-L6-v2
    display_name: MiniLM L6 v2
    huggingface_repo: sentence-transformers/all-MiniLM-L6-v2
    dimensions: 384
    max_seq_length: 256
    description: 'Fast, lightweight (23MB). Good general purpose.'
  # ... more models
```

Changing the model in the YAML file directly won't trigger a reindex — use the Settings UI to switch properly.
