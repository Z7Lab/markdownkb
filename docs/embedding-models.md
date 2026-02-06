# Embedding Models

mdkb uses ONNX-based embedding models for semantic search. All models run locally on CPU — no GPU or external API required.

## Available Models

| Model | Dimensions | Max Tokens | Size | Notes |
|-------|-----------|------------|------|-------|
| all-MiniLM-L6-v2 | 384 | 256 | ~23 MB | Default. Fast, good general quality. |
| all-MiniLM-L12-v2 | 384 | 256 | ~33 MB | Better quality, same dimensions as L6. Slightly slower. |
| bge-small-en-v1.5 | 384 | 512 | ~33 MB | Best retrieval quality. Longer context window. |

All three models output 384-dimensional vectors, so switching between them doesn't require schema changes — just a full reindex.

## Switching Models

From the **Settings** tab in the UI:

1. Find the **Embedding Model** panel
2. If the model you want shows "Not installed", click **Install** (downloads from HuggingFace)
3. Click **Use** on an installed model
4. Confirm the reindex warning — switching clears all indexed data and reindexes every document
5. Progress updates appear in the status area while reindexing runs in the background

You can continue using the app while reindexing. The cancel button in the Index panel will stop a running reindex.

## CPU Usage

Embedding and indexing are CPU-bound operations. mdkb limits resource usage by:

- Setting ONNX inference threads to half your CPU cores (`intra_op_num_threads`, `inter_op_num_threads`)
- Throttling the indexing loop with a small sleep between files
- Setting `OMP_NUM_THREADS` to prevent OpenMP from spawning too many threads

For large collections (1000+ files), expect reindexing to take a few minutes.

## Storage

Models are cached locally:

- **mdkb models:** `~/.cache/mdkb/models/{model-id}/`
- **ChromaDB built-in L6:** `~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/` (detected automatically if present)

The active model is stored in `config/settings.yaml` under `embeddings.model`.

## Config

In `config/settings.yaml`:

```yaml
embeddings:
  model: all-MiniLM-L6-v2   # or all-MiniLM-L12-v2, bge-small-en-v1.5
  chunk_size: 512
  chunk_overlap: 50
```

Changing the model in the YAML file directly won't trigger a reindex — use the Settings UI to switch properly.
