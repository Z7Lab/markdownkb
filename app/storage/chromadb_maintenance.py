"""ChromaDB maintenance helpers: orphaned chunk and segment detection/cleanup."""

import shutil
import sqlite3
from pathlib import Path


def get_orphaned_segment_dirs(chroma_dir: str) -> list[tuple[str, int]]:
    """Return (dir_path, size_bytes) for each orphaned HNSW segment directory.

    Orphaned dirs are UUID-named subdirectories in the chromadb folder with no
    matching row in the segments table — left behind when a collection or bucket
    is deleted because ChromaDB never removes them automatically.
    """
    chroma_path = Path(chroma_dir)
    db_path = chroma_path / "chroma.sqlite3"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path), timeout=5.0)
    active_segments = {row[0] for row in conn.execute("SELECT id FROM segments")}
    conn.close()

    orphans = []
    for entry in sorted(chroma_path.iterdir()):
        if not entry.is_dir():
            continue
        # Segment dirs are named as UUIDs — skip anything else (e.g. "index/")
        parts = entry.name.split("-")
        if len(parts) != 5 or not all(p.isalnum() for p in parts):
            continue
        if entry.name not in active_segments:
            size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
            orphans.append((str(entry), size))
    return orphans


def get_orphaned_chunk_info(collection) -> tuple[list[str], set[str]]:
    """Return (chunk_ids, source_paths) for chunks whose source file is gone.

    Accepts a ChromaDB collection object. Scans all chunk metadata and
    identifies entries whose source_path no longer exists on disk.
    """
    all_data = collection.get(include=["metadatas"])
    orphan_ids: list[str] = []
    orphan_sources: set[str] = set()
    for chunk_id, meta in zip(all_data["ids"], all_data["metadatas"]):
        src = meta.get("source_path", "")
        if src and not src.startswith("bucket://") and not Path(src).exists():
            orphan_ids.append(chunk_id)
            orphan_sources.add(src)
    return orphan_ids, orphan_sources


def estimate_vacuum_savings(chroma_dir: str) -> int:
    """Return estimated bytes recoverable by VACUUMing chroma.sqlite3."""
    db_path = Path(chroma_dir) / "chroma.sqlite3"
    if not db_path.exists():
        return 0
    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        free_pages = conn.execute("PRAGMA freelist_count").fetchone()[0]
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        conn.close()
        return free_pages * page_size
    except OSError:
        return 0


def vacuum_chromadb(chroma_dir: str) -> tuple[bool, int]:
    """Checkpoint WAL and VACUUM chroma.sqlite3.

    Returns (success, bytes_freed). The VACUUM requires a brief exclusive
    lock; it may fail if ChromaDB is actively writing. Returns (False, 0)
    on failure so callers can surface a retry message.
    """
    db_path = Path(chroma_dir) / "chroma.sqlite3"
    if not db_path.exists():
        return False, 0
    before = db_path.stat().st_size
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("VACUUM")
        conn.close()
    except Exception:
        return False, 0
    after = db_path.stat().st_size
    return True, max(before - after, 0)


def delete_orphaned_segments(chroma_dir: str) -> tuple[int, int]:
    """Delete orphaned HNSW segment directories. Returns (count, bytes_freed)."""
    orphans = get_orphaned_segment_dirs(chroma_dir)
    freed = 0
    for dir_path, size in orphans:
        shutil.rmtree(dir_path, ignore_errors=True)
        freed += size
    return len(orphans), freed
