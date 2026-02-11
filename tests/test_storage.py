"""Unit tests for storage-layer rename operations (TrackingDB + VectorStore)."""

import tempfile

import pytest

from app.storage.trackingdb import TrackingDB
from app.storage.vectorstore import VectorStore


@pytest.fixture
def tracking(tmp_path):
    db = TrackingDB(str(tmp_path))
    yield db
    db.close()


@pytest.fixture
def store(tmp_path):
    return VectorStore(
        persist_directory=str(tmp_path / "chroma"),
        collection_name="test",
    )


# --- TrackingDB.rename_file ---

class TestTrackingRename:
    def test_rename_preserves_fields(self, tracking):
        tracking.upsert_file(
            "/old/path.md", "/old", "hash123", 512, 1700000000.0,
            status="complete", chunk_count=5,
        )
        tracking.set_include_rag("/old/path.md", False)

        result = tracking.rename_file("/old/path.md", "/new/path.md", "/new")
        assert result is True

        old = tracking.get_file("/old/path.md")
        assert old is None

        new = tracking.get_file("/new/path.md")
        assert new is not None
        assert new["source_root"] == "/new"
        assert new["content_hash"] == "hash123"
        assert new["file_size"] == 512
        assert new["chunk_count"] == 5
        assert new["status"] == "complete"
        assert new["include_rag"] == 0  # preserved exclusion

    def test_rename_nonexistent_returns_false(self, tracking):
        result = tracking.rename_file("/nope.md", "/new.md", "/new")
        assert result is False

    def test_rename_updates_source_root(self, tracking):
        tracking.upsert_file(
            "/src1/file.md", "/src1", "h", 100, 1.0,
            status="complete", chunk_count=2,
        )
        tracking.rename_file("/src1/file.md", "/src2/file.md", "/src2")

        rec = tracking.get_file("/src2/file.md")
        assert rec["source_root"] == "/src2"


# --- VectorStore.rename_source ---

class TestVectorStoreRename:
    def _add_chunks(self, store, path, source_root, count=3):
        """Helper to add test chunks for a file."""
        ids = [f"{path}::section_{i}::{i}" for i in range(count)]
        docs = [f"Content of chunk {i}" for i in range(count)]
        # Simple fake embeddings (384-dim like MiniLM)
        embeddings = [[float(i + j) / 100 for j in range(384)] for i in range(count)]
        metadatas = [
            {"source_path": path, "source_root": source_root,
             "heading": f"section_{i}", "chunk_index": i}
            for i in range(count)
        ]
        store.add(ids, docs, embeddings, metadatas)
        return ids, embeddings

    def test_rename_preserves_chunks(self, store):
        old_ids, old_embeddings = self._add_chunks(
            store, "/old/file.md", "/old", count=3,
        )
        assert store.count == 3

        moved = store.rename_source("/old/file.md", "/new/file.md", "/new")
        assert moved == 3
        assert store.count == 3  # same count, not duplicated

        # Verify old path chunks are gone
        metas = store.get_all_metadatas()
        paths = {m["source_path"] for m in metas}
        assert "/old/file.md" not in paths
        assert "/new/file.md" in paths

        # Verify metadata updated
        for m in metas:
            assert m["source_root"] == "/new"

    def test_rename_nonexistent_returns_zero(self, store):
        result = store.rename_source("/nope.md", "/new.md", "/new")
        assert result == 0

    def test_rename_preserves_embeddings(self, store):
        """Verify embeddings survive the rename (no re-embedding needed)."""
        old_ids, old_embeddings = self._add_chunks(
            store, "/old/file.md", "/old", count=2,
        )

        # Get embeddings before rename
        before = store._collection.get(
            where={"source_path": "/old/file.md"},
            include=["embeddings"],
        )

        store.rename_source("/old/file.md", "/new/file.md", "/new")

        # Get embeddings after rename
        after = store._collection.get(
            where={"source_path": "/new/file.md"},
            include=["embeddings"],
        )

        assert len(after["embeddings"]) == 2
        # Embeddings should be identical (minor float32 precision loss is ok)
        for emb_before, emb_after in zip(
            sorted(before["embeddings"], key=lambda e: e[0]),
            sorted(after["embeddings"], key=lambda e: e[0]),
        ):
            assert len(emb_before) == len(emb_after)
            for a, b in zip(emb_before, emb_after):
                assert abs(float(a) - float(b)) < 1e-6

    def test_rename_updates_chunk_ids(self, store):
        self._add_chunks(store, "/old/file.md", "/old", count=2)
        store.rename_source("/old/file.md", "/new/file.md", "/new")

        result = store._collection.get(
            where={"source_path": "/new/file.md"},
        )
        for chunk_id in result["ids"]:
            assert chunk_id.startswith("/new/file.md::")
            assert "/old/file.md" not in chunk_id
