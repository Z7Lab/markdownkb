# Embedding Models

Embedding models convert your documents into numerical vectors that power semantic search. They're **separate from the chat model** — you need an embedding model to index and search, but it doesn't need to be the same provider as your chat LLM.

## What is ONNX?

ONNX (Open Neural Network Exchange) is a portable model format that runs on any CPU without a GPU or external service. MarkdownKB uses ONNX for local embeddings — the models are small (23-133 MB), fast, and work offline.

Models are downloaded from [HuggingFace](https://huggingface.co) on first install via Settings > Embedding Model. They're stored in the data directory (`{data_directory}/models/`).

## Providers

MarkdownKB supports three embedding providers:

- **Local ONNX (default)** — runs on CPU, no external service needed, works offline
- **Ollama** — use an Ollama embedding model (e.g. `nomic-embed-text`), local or remote
- **OpenAI-compatible API** — any endpoint serving `/v1/embeddings` (Venice, OpenAI, Together, etc.)

Configure the provider via **Settings → Embedding Model** in the web UI. To set a provider before first run, add it to `config/settings.yaml` under the `embeddings:` section.

## Remote Embeddings

Point to an Ollama instance or OpenAI-compatible endpoint to offload embedding work to a faster machine.

### Ollama

1. On the remote machine, install Ollama and pull an embedding model:
   ```bash
   ollama pull nomic-embed-text
   ```
2. In MarkdownKB Settings > Embedding Model, select **Ollama** from the Provider dropdown
3. Set API Base to the Ollama URL (e.g. `http://192.168.x.x:11434`)
4. Set Model to `nomic-embed-text`
5. Click "Test" to verify, then "Save"

### OpenAI-compatible API (Venice, OpenAI, Together, Voyage, etc.)

Any endpoint serving `POST /v1/embeddings` works — including cloud providers like Venice, OpenAI, Together, and Voyage.

1. In MarkdownKB Settings > Embedding Model, select **OpenAI-compatible API** from the Provider dropdown
2. Set API Base to the provider's URL (e.g. `https://api.venice.ai/api/v1`)
3. Set Model to the embedding model name (e.g. `text-embedding-3-small`)
4. Enter your API Key (required for authenticated providers)
5. Click "Test" to verify, then "Save"

API keys can also be configured via Docker secrets (`secrets/embedding_api_key`) or environment variable (`EMBEDDING_API_KEY`), following the same pattern as chat model API keys.

### Config examples

**Ollama (local network, no auth):**
```yaml
embeddings:
  provider: remote
  api_base: http://<your-server-ip>:11434  # Replace with your embedding server IP
  remote_model: nomic-embed-text
  api_type: ollama
```

**Venice (cloud, authenticated):**
```yaml
embeddings:
  provider: remote
  api_base: https://api.venice.ai/api/v1
  remote_model: text-embedding-3-small
  api_type: openai
  # API key via secrets/embedding_api_key or EMBEDDING_API_KEY env var
```

## Local ONNX Models

Local models run on CPU with no external API required.

## Auto-Download

On first startup, MarkdownKB automatically downloads the configured embedding model from HuggingFace. You'll see download progress in the logs:

```
Embedding model 'all-MiniLM-L6-v2' not found, downloading...
  onnx/model.onnx: 45.2 MB / 90.4 MB (50%)
  onnx/model.onnx: 90.4 MB / 90.4 MB (100%)
  tokenizer.json: 711.2 KB downloaded
Embedding model 'all-MiniLM-L6-v2' installed
```

No manual install step is needed. You can also install additional models from the Settings UI.

## Built-in Models

These are available out of the box:

| Model | Dimensions | Max Tokens | ~Max Chars | Size | Notes |
|-------|-----------|------------|------------|------|-------|
| all-MiniLM-L6-v2 | 384 | 256 | ~1000 | ~23 MB | Fast, lightweight. Good general quality. |
| all-MiniLM-L12-v2 | 384 | 256 | ~1000 | ~33 MB | Better quality than L6, same dimensions. Slightly slower. |
| bge-small-en-v1.5 | 384 | 512 | ~2000 | ~133 MB | Fast, good retrieval quality. 512 token context. |
| nomic-embed-text-v1.5 | 768 | 8192 | ~32000 | ~130 MB | **Recommended.** Best retrieval quality (21% better MTEB than bge-small). 8192 token context handles long documents without truncation. |

MiniLM and BGE output 384-dimensional vectors and are interchangeable without schema changes (just re-index). Nomic uses 768-dimensional vectors — switching to or from it requires clearing the vector store and re-indexing.

## Chunk Size and Model Capacity

The `chunk_size` setting (in characters) controls how documents are split before embedding. This interacts directly with the model's `max_seq_length` (in tokens):

- **If chunks exceed the model's token limit**, the model silently truncates the input. The tail of each chunk is never embedded, which degrades search quality — queries about content near the end of a chunk won't match.
- **Rule of thumb**: 1 token ~ 4 characters for English text. A 512-token model handles ~2000 characters; a 256-token model handles ~1000 characters.

### Recommended pairings

| Model | Max Tokens | Recommended chunk_size |
|-------|-----------|----------------------|
| MiniLM (L6/L12) | 256 | 800–1000 |
| bge-small-en-v1.5 | 512 | 1200–1500 |
| nomic-embed-text-v1.5 | 8192 | 1500–4000 |

The default configuration uses `chunk_size: 1500`. With nomic-embed-text-v1.5 you can increase this significantly — the model handles documents up to ~32,000 characters without truncation. If you switch to a MiniLM model, reduce `chunk_size` to 1000 or less to avoid silent truncation.

### How to tell if chunks are being truncated

After indexing, check the chunk size distribution from the Files tab. If many chunks are near or above the model's character limit (~1000 for MiniLM, ~2000 for BGE), the tails are being truncated. A well-configured setup has most chunks well below the limit.

## Switching Models

From the **Settings** tab in the UI:

1. Find the **Embedding Model** panel
2. If the model you want shows "Not installed", click **Install** (downloads from HuggingFace or copies from local path)
3. Click **Use** on an installed model
4. Confirm the reindex warning — switching clears all indexed data and reindexes every document
5. Progress updates appear in the status area while reindexing runs in the background

You can continue using the app while reindexing. The cancel button in the Index panel will stop a running reindex.

## Adding Custom Models

Custom models are defined under `embeddings.models` in `config/settings.yaml` (for first-run seed) or directly in the settings database. You can add any ONNX sentence-transformer model from HuggingFace.

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

The directory must contain all required files (by default: `onnx/model.onnx`, `tokenizer.json`, etc.). Files are copied into `{data_directory}/models/` on install — the original directory is not modified.

This is useful for:
- Air-gapped / offline deployments
- Pre-downloaded models shared across machines
- Custom fine-tuned models not on HuggingFace

## CPU Usage

Embedding and indexing are CPU-bound operations. MarkdownKB limits resource usage by:

- Setting ONNX inference threads to half your CPU cores (`intra_op_num_threads`, `inter_op_num_threads`)
- Throttling the indexing loop with a small sleep between files
- Setting `OMP_NUM_THREADS` to prevent OpenMP from spawning too many threads

For large collections (1000+ files), expect reindexing to take a few minutes.

## Storage

Models are stored at `{data_directory}/models/{model-id}/`. The data directory is resolved via `MARKDOWNKB_DATA_DIR` env var or OS-appropriate default (see [configuration](../reference/configuration.md#storage)).

The active model is stored in the settings database. Change it via **Settings → Embedding Model**.

## Config

The equivalent `config/settings.yaml` structure (for first-run seed):

```yaml
embeddings:
  model: bge-small-en-v1.5   # or any model_id from the models list
  chunk_size: 1500
  chunk_overlap: 50
  models:
  - model_id: bge-small-en-v1.5
    display_name: BGE Small EN v1.5
    huggingface_repo: BAAI/bge-small-en-v1.5
    dimensions: 384
    max_seq_length: 512
    query_prefix: 'Represent this sentence for searching relevant passages: '
    description: 'Best retrieval quality (133MB). 512 token context.'
  - model_id: all-MiniLM-L6-v2
    display_name: MiniLM L6 v2
    huggingface_repo: sentence-transformers/all-MiniLM-L6-v2
    dimensions: 384
    max_seq_length: 256
    description: 'Fast, lightweight (23MB). Good general purpose.'
  # ... more models
```

Changing the model in the YAML file directly won't trigger a reindex — use the Settings UI to switch properly.

## Removing Models

Installed models can be removed from the Settings UI:

1. In the **Embedding Model** panel, find the model you want to remove
2. Click the trash icon next to it (only available for installed, non-active models)
3. Confirm the removal

This deletes the model files from `{data_directory}/models/`. You can re-download it later. The active model cannot be removed — switch to a different model first.

## Corrupt or Missing Models

If a model file is corrupt (e.g., incomplete download), the app handles it gracefully:

- **On startup**: If the active model fails to load, the app logs the error and starts anyway. Fix the model from Settings.
- **Detection**: The downloader validates that ONNX files are at least 1 KB. Files below this are treated as missing.
- **Recovery**: Remove the corrupt model from Settings (trash icon), then reinstall it.
