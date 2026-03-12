"""Generic ONNX-based text embedding with model switching."""

import logging
import os
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from app.embeddings.downloader import get_model_path, is_installed
from app.embeddings.registry import get_model_info

logger = logging.getLogger(__name__)

_DEFAULT_THREADS = str(max(1, (os.cpu_count() or 4) // 2))
os.environ.setdefault("OMP_NUM_THREADS", _DEFAULT_THREADS)


def _resolve(base: Path, primary: str) -> Path:
    """Resolve a file path, falling back to onnx/ subdir (ChromaDB layout)."""
    p = base / primary
    if p.exists():
        return p
    alt = base / "onnx" / primary
    if alt.exists():
        return alt
    raise FileNotFoundError(f"Cannot find {primary} in {base}")


class ONNXEmbedder:
    """Generic ONNX embedding function for any supported model."""

    def __init__(self, model_id: str):
        info = get_model_info(model_id)
        base = get_model_path(model_id)

        self._model_id = model_id
        self._dimensions = info.dimensions
        self._max_seq_length = info.max_seq_length
        self._query_prefix = info.query_prefix

        # Load tokenizer
        tok_path = _resolve(base, info.tokenizer_path)
        self._tokenizer = Tokenizer.from_file(str(tok_path))
        self._tokenizer.enable_truncation(max_length=self._max_seq_length)
        self._tokenizer.enable_padding(
            pad_id=0, pad_token="[PAD]", length=self._max_seq_length,
        )

        # Load ONNX session (limit threads to avoid pegging CPU)
        _threads = int(_DEFAULT_THREADS)
        so = ort.SessionOptions()
        so.log_severity_level = 3
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        so.intra_op_num_threads = _threads
        so.inter_op_num_threads = _threads

        providers = [
            p for p in ort.get_available_providers()
            if p != "CoreMLExecutionProvider"
        ]

        onnx_file = _resolve(base, info.onnx_path)
        try:
            self._session = ort.InferenceSession(
                str(onnx_file), providers=providers, sess_options=so,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to load ONNX model '{model_id}' from {onnx_file}. "
                f"The file may be corrupt — try removing and re-downloading "
                f"from Settings. Original error: {e}"
            ) from e

        # Check if model accepts token_type_ids
        input_names = {inp.name for inp in self._session.get_inputs()}
        self._use_token_type_ids = "token_type_ids" in input_names

        logger.info(
            "Loaded embedding model: %s (dims=%d, max_seq=%d)",
            model_id, self._dimensions, self._max_seq_length,
        )

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Embed a list of texts. Returns list of float vectors."""
        if not texts:
            return []

        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            encoded = [self._tokenizer.encode(t) for t in batch]

            input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
            attention_mask = np.array(
                [e.attention_mask for e in encoded], dtype=np.int64,
            )

            onnx_input = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            }
            if self._use_token_type_ids:
                onnx_input["token_type_ids"] = np.zeros_like(
                    input_ids, dtype=np.int64,
                )

            outputs = self._session.run(None, onnx_input)
            last_hidden_state = outputs[0]

            # Mean pooling with attention mask
            mask_expanded = np.broadcast_to(
                np.expand_dims(attention_mask, -1), last_hidden_state.shape,
            )
            pooled = (
                np.sum(last_hidden_state * mask_expanded, axis=1)
                / np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
            )

            # L2 normalize
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            norms = np.clip(norms, a_min=1e-12, a_max=None)
            normalized = (pooled / norms).astype(np.float32)

            all_embeddings.append(normalized)

        result = np.concatenate(all_embeddings)
        return [row.tolist() for row in result]


class _EmbedderManager:
    """Manages the active embedder singleton with model switching."""

    def __init__(self):
        self._embedder: ONNXEmbedder | None = None
        self._model_id: str | None = None

    def get(self, model_id: str) -> ONNXEmbedder:
        """Return the embedder for the given model, loading if needed."""
        if self._embedder is None or self._model_id != model_id:
            if not is_installed(model_id):
                raise RuntimeError(
                    f"Model '{model_id}' is not installed. "
                    "Install it from Settings before switching."
                )
            self._embedder = ONNXEmbedder(model_id)
            self._model_id = model_id
        return self._embedder

    def clear(self):
        """Unload the current model to free memory."""
        self._embedder = None
        self._model_id = None


_manager = _EmbedderManager()


def embed_texts(
    texts: list[str], model_id: str = "all-MiniLM-L6-v2",
) -> list[list[float]]:
    """Embed a list of text strings into vectors."""
    return _manager.get(model_id).embed(texts)


def embed_query(
    query: str, model_id: str = "all-MiniLM-L6-v2",
) -> list[float]:
    """Embed a single query string into a vector."""
    embedder = _manager.get(model_id)
    text = embedder._query_prefix + query if embedder._query_prefix else query
    return embedder.embed([text])[0]


def unload_model():
    """Unload the current embedding model from memory."""
    _manager.clear()
