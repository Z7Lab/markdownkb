#!/usr/bin/env python3
"""
Embedding benchmark: bge-small-en-v1.5 vs nomic-embed-text-v1.5 (fp16 ONNX)

Runs inside Docker so models and sources are at their production paths.
Downloads nomic to /data/models/bench/ (persists in volume — no re-download).
Writes to two isolated /tmp ChromaDB dirs — leaves your main ChromaDB untouched.
If you decide not to switch, nothing changes.

Usage (run inside Docker):
    docker exec markdownkb .venv/bin/python scripts/benchmark_embeddings.py
    docker exec markdownkb .venv/bin/python scripts/benchmark_embeddings.py --sample 100
    docker exec markdownkb .venv/bin/python scripts/benchmark_embeddings.py --keep
"""

import argparse
import json
import os
import random
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ingestion.parser import parse_and_chunk

# Model dirs (inside Docker volume)
DATA_DIR = Path(os.environ.get("MARKDOWNKB_DATA_DIR", "/data"))
BGE_DIR = DATA_DIR / "models" / "bge-small-en-v1.5"
NOMIC_DIR = DATA_DIR / "models" / "bench" / "nomic-embed-text-v1.5"

NOMIC_REPO = "nomic-ai/nomic-embed-text-v1.5"
NOMIC_FILES = [
    "onnx/model_fp16.onnx",  # ~274MB — fp16 for lower memory
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "config.json",
]
HF_URL = "https://huggingface.co/{repo}/resolve/main/{path}"


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_nomic(dest: Path) -> None:
    for rel in NOMIC_FILES:
        out = dest / rel
        if out.exists() and out.stat().st_size > 1024:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        url = HF_URL.format(repo=NOMIC_REPO, path=rel)
        print(f"  Downloading {rel}...", flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "mdkb-bench/1.0"})
        tmp = out.with_suffix(".tmp")
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(tmp, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded * 100 // total
                            mb = downloaded // 1048576
                            print(f"\r    {pct}% ({mb}MB / {total // 1048576}MB)   ", end="", flush=True)
            print()
            tmp.rename(out)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise


# ---------------------------------------------------------------------------
# Embedder
# ---------------------------------------------------------------------------

class BenchEmbedder:
    """Minimal ONNX embedder — no app registry required."""

    def __init__(self, model_dir: Path, max_seq: int, pad_to_max: bool):
        tok_file = model_dir / "tokenizer.json"
        if not tok_file.exists():
            raise FileNotFoundError(f"tokenizer.json not found in {model_dir}")

        self._tok = Tokenizer.from_file(str(tok_file))

        # Detect pad token from tokenizer_config.json
        pad_token = "[PAD]"
        pad_id = 0
        cfg_file = model_dir / "tokenizer_config.json"
        if cfg_file.exists():
            cfg = json.loads(cfg_file.read_text())
            pt = cfg.get("pad_token")
            if isinstance(pt, str):
                pad_token = pt
            elif isinstance(pt, dict):
                pad_token = pt.get("content", "[PAD]")

        self._tok.enable_truncation(max_length=max_seq)
        if pad_to_max:
            # bge-small: pad all to 512 (what the production embedder does)
            self._tok.enable_padding(pad_id=pad_id, pad_token=pad_token, length=max_seq)
        else:
            # nomic: pad to longest in batch — avoids 8192-length tensors
            self._tok.enable_padding(pad_id=pad_id, pad_token=pad_token)

        onnx_files = sorted(model_dir.rglob("*.onnx"))
        if not onnx_files:
            raise FileNotFoundError(f"No .onnx file found in {model_dir}")
        # Prefer fp16
        fp16 = [f for f in onnx_files if "fp16" in f.name]
        onnx_file = fp16[0] if fp16 else onnx_files[0]

        threads = max(1, (os.cpu_count() or 4) // 2)
        so = ort.SessionOptions()
        so.log_severity_level = 3
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = threads
        self._sess = ort.InferenceSession(str(onnx_file), sess_options=so)
        self._use_tti = "token_type_ids" in {i.name for i in self._sess.get_inputs()}
        size_mb = onnx_file.stat().st_size // 1048576
        print(f"  Loaded {onnx_file.name} ({size_mb}MB), token_type_ids={self._use_tti}")

    def embed(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        all_embs: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            enc = [self._tok.encode(t) for t in batch]
            input_ids = np.array([e.ids for e in enc], dtype=np.int64)
            attn = np.array([e.attention_mask for e in enc], dtype=np.int64)
            inp: dict = {"input_ids": input_ids, "attention_mask": attn}
            if self._use_tti:
                inp["token_type_ids"] = np.zeros_like(input_ids, dtype=np.int64)
            hidden = self._sess.run(None, inp)[0]  # (batch, seq, dim)
            mask = np.broadcast_to(np.expand_dims(attn, -1), hidden.shape)
            pooled = np.sum(hidden * mask, axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            normalized = (pooled / np.clip(norms, 1e-12, None)).astype(np.float32)
            all_embs.extend(normalized.tolist())
        return all_embs


# ---------------------------------------------------------------------------
# Trial
# ---------------------------------------------------------------------------

def run_trial(label: str, embedder: BenchEmbedder, chunks: list[str], db_dir: Path) -> dict:
    import chromadb

    print(f"\n[{label}] embedding {len(chunks)} chunks...")
    db_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(db_dir))
    col_name = label.replace(" ", "_").replace(".", "_").replace("-", "_").lower()
    col = client.get_or_create_collection(col_name, metadata={"hnsw:space": "cosine"})

    t0 = time.perf_counter()
    embeddings = embedder.embed(chunks)
    t_embed = time.perf_counter() - t0
    print(f"  Embedding done: {t_embed:.1f}s")

    t1 = time.perf_counter()
    batch = 500
    for i in range(0, len(chunks), batch):
        ids = [f"c{j}" for j in range(i, min(i + batch, len(chunks)))]
        col.add(ids=ids, documents=chunks[i:i + batch], embeddings=embeddings[i:i + batch])
    t_db = time.perf_counter() - t1
    print(f"  DB write done:  {t_db:.1f}s")

    total = t_embed + t_db
    return {
        "embed_s": t_embed,
        "db_s": t_db,
        "total_s": total,
        "chunks_per_s": len(chunks) / total,
        "db_dir": db_dir,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", type=int, default=50, metavar="N", help="Files to sample (default: 50)")
    parser.add_argument("--keep", action="store_true", help="Keep temp ChromaDB dirs after run")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible sampling")
    args = parser.parse_args()

    random.seed(args.seed)

    # Read sources + chunk settings from settings.yaml
    cfg_file = ROOT / "config" / "settings.yaml"
    with open(cfg_file) as f:
        cfg = yaml.safe_load(f)
    raw_sources = cfg.get("sources", [])
    source_paths = [s["path"] if isinstance(s, dict) else s for s in raw_sources]
    chunk_size = cfg.get("embeddings", {}).get("chunk_size", 1500)
    chunk_overlap = cfg.get("embeddings", {}).get("chunk_overlap", 150)

    # Collect and sample files
    all_files: list[Path] = []
    for src in source_paths:
        p = Path(src)
        if p.exists():
            all_files.extend(p.rglob("*.md"))
    print(f"Found {len(all_files)} markdown files across {len(source_paths)} sources")

    sample = random.sample(all_files, min(args.sample, len(all_files)))
    print(f"Sampled {len(sample)} files (seed={args.seed}, chunk_size={chunk_size})")

    # Parse chunks — same for both trials
    print("Parsing chunks...", flush=True)
    all_chunks: list[str] = []
    for f in sample:
        src_root = str(f.parent)
        chunks = parse_and_chunk(str(f), source_root=src_root,
                                 max_chunk_size=chunk_size, overlap=chunk_overlap)
        all_chunks.extend(c.content for c in chunks)
    print(f"Total chunks: {len(all_chunks)}  (avg {len(all_chunks) // len(sample)} per file)")

    ts = int(time.time())
    bge_db = Path(f"/tmp/mdkb-bench-bge-{ts}")
    nomic_db = Path(f"/tmp/mdkb-bench-nomic-{ts}")

    # --- bge-small ---
    print(f"\n=== bge-small-en-v1.5 (384-dim, 512-token max) ===")
    if not BGE_DIR.exists():
        print(f"ERROR: bge-small not found at {BGE_DIR}")
        print("Install it from the Settings page first.")
        sys.exit(1)
    bge = BenchEmbedder(BGE_DIR, max_seq=512, pad_to_max=True)
    bge_r = run_trial("bge_small_en_v1_5", bge, all_chunks, bge_db)
    del bge

    # --- nomic ---
    print(f"\n=== nomic-embed-text-v1.5 fp16 (768-dim, 8192-token max) ===")
    if not all((NOMIC_DIR / f).exists() for f in NOMIC_FILES):
        print(f"Downloading nomic-embed-text-v1.5 to {NOMIC_DIR}...")
        download_nomic(NOMIC_DIR)
    else:
        print(f"  Using cached model at {NOMIC_DIR}")
    nomic = BenchEmbedder(NOMIC_DIR, max_seq=8192, pad_to_max=False)
    nomic_r = run_trial("nomic_embed_text_v1_5", nomic, all_chunks, nomic_db)
    del nomic

    # --- Results ---
    total_files = len(all_files)
    print("\n" + "=" * 62)
    print(f"  RESULTS  —  {len(sample)} files / {len(all_chunks)} chunks sampled")
    print("=" * 62)
    for label, r in [("bge-small-en-v1.5  (384-dim)", bge_r), ("nomic-embed-text fp16  (768-dim)", nomic_r)]:
        proj_min = (total_files * r["total_s"] / len(sample)) / 60
        print(f"\n  {label}")
        print(f"    Embedding :  {r['embed_s']:.1f}s")
        print(f"    DB write  :  {r['db_s']:.1f}s")
        print(f"    Total     :  {r['total_s']:.1f}s  →  {r['chunks_per_s']:.1f} chunks/s")
        print(f"    Projected full reindex ({total_files} files):  ~{proj_min:.0f} min")

    ratio = nomic_r["total_s"] / bge_r["total_s"]
    print(f"\n  nomic is {ratio:.1f}x slower than bge-small on this hardware")
    print(f"  Nomic model cached at: {NOMIC_DIR}  (delete to free space)")
    print()

    if args.keep:
        print(f"  BGE   DB: {bge_db}")
        print(f"  Nomic DB: {nomic_db}")
    else:
        shutil.rmtree(bge_db, ignore_errors=True)
        shutil.rmtree(nomic_db, ignore_errors=True)
        print("  Temp ChromaDB dirs cleaned up (--keep to retain)")

    print("\n  Main ChromaDB: untouched.")


if __name__ == "__main__":
    main()
