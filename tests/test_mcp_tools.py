"""Tests for MCP tool discovery, read-only mode, and retrieve_documents tool."""

from unittest.mock import MagicMock

from tests.conftest import FakeResult, FakeSettings


# ---------------------------------------------------------------------------
# Tool discovery & read-only flag
# ---------------------------------------------------------------------------

class TestToolDiscovery:
    """Tests for app.mcp.tools.discover_tools."""

    def test_discover_finds_core_tools(self):
        from app.mcp.tools import discover_tools

        settings = FakeSettings()
        tools, _errors = discover_tools(settings)
        names = [t["name"] for t in tools]

        assert "search" in names
        assert "get_file" in names
        assert "list_files" in names
        assert "search_documents" in names
        assert "plan" in names

    def test_requires_plugin_disables_when_plugin_off(self):
        from app.mcp.tools import discover_tools

        settings = FakeSettings()
        settings.set_plugin_enabled("planner", False)

        tools, _errors = discover_tools(settings)
        by_name = {t["name"]: t for t in tools}

        assert by_name["plan"]["enabled"] is False
        assert by_name["plan"]["requires_plugin"] == "planner"

    def test_requires_plugin_enables_when_plugin_on(self):
        from app.mcp.tools import discover_tools

        settings = FakeSettings()
        settings.set_plugin_enabled("planner", True)

        tools, _errors = discover_tools(settings)
        by_name = {t["name"]: t for t in tools}

        assert by_name["plan"]["enabled"] is True

    def test_write_tools_marked(self):
        from app.mcp.tools import discover_tools

        settings = FakeSettings()
        tools, _errors = discover_tools(settings)
        by_name = {t["name"]: t for t in tools}

        assert by_name["index_file"]["write"] is True
        assert by_name["save_file"]["write"] is True
        assert by_name["search"]["write"] is False

    def test_read_only_disables_write_tools(self):
        from app.mcp.tools import discover_tools

        settings = FakeSettings()
        settings._mcp["read_only"] = True

        tools, _errors = discover_tools(settings)
        by_name = {t["name"]: t for t in tools}

        # Write tools should be disabled
        assert by_name["index_file"]["enabled"] is False
        assert by_name["save_file"]["enabled"] is False

        # Read tools should remain enabled
        assert by_name["search"]["enabled"] is True
        assert by_name["get_file"]["enabled"] is True
        assert by_name["search_documents"]["enabled"] is True

    def test_read_only_false_allows_write_tools(self):
        from app.mcp.tools import discover_tools

        settings = FakeSettings()
        settings._mcp["read_only"] = False
        # save_document needs its own feature flag enabled
        settings._mcp["save_document"] = True

        tools, _errors = discover_tools(settings)
        by_name = {t["name"]: t for t in tools}

        assert by_name["index_file"]["enabled"] is True
        assert by_name["save_file"]["enabled"] is True

    def test_feature_flag_still_disables_when_not_read_only(self):
        """save_document should be disabled by its own feature flag even when read_only is off."""
        from app.mcp.tools import discover_tools

        settings = FakeSettings()
        settings._mcp["read_only"] = False
        settings._mcp["save_document"] = False

        tools, _errors = discover_tools(settings)
        by_name = {t["name"]: t for t in tools}

        assert by_name["save_file"]["enabled"] is False
        assert by_name["index_file"]["enabled"] is True

    def test_read_only_blocks_bucket_writes_by_default(self):
        """Bucket write tools blocked under read_only when allow_bucket_writes is off."""
        from app.mcp.tools import discover_tools

        settings = FakeSettings()
        settings._mcp["read_only"] = True
        settings._mcp["allow_bucket_writes"] = False
        settings.set_plugin_enabled("buckets", True)

        tools, _errors = discover_tools(settings)
        by_name = {t["name"]: t for t in tools}

        assert by_name["bucket_create"]["enabled"] is False
        assert by_name["bucket_delete"]["enabled"] is False
        # Read-only bucket tools should still work
        assert by_name["bucket_list"]["enabled"] is True
        assert by_name["bucket_search"]["enabled"] is True

    def test_allow_bucket_writes_exempts_bucket_tools(self):
        """Bucket write tools allowed under read_only when allow_bucket_writes is true."""
        from app.mcp.tools import discover_tools

        settings = FakeSettings()
        settings._mcp["read_only"] = True
        settings._mcp["allow_bucket_writes"] = True
        settings._mcp["save_document"] = True
        settings.set_plugin_enabled("buckets", True)

        tools, _errors = discover_tools(settings)
        by_name = {t["name"]: t for t in tools}

        # Bucket write tools should be allowed
        assert by_name["bucket_create"]["enabled"] is True
        assert by_name["bucket_delete"]["enabled"] is True
        # Non-bucket write tools should still be blocked
        assert by_name["save_file"]["enabled"] is False
        assert by_name["index_file"]["enabled"] is False


# ---------------------------------------------------------------------------
# retrieve_documents tool
# ---------------------------------------------------------------------------

class TestSearchDocuments:
    """Tests for the retrieve_documents MCP tool handler."""

    def _make_context(self, retriever, tracking):
        """Build a fake MCP context matching what tools expect."""
        from tests.conftest import FakeSettings
        ctx = MagicMock()
        ctx.request_context.lifespan_context = {
            "retriever": retriever,
            "tracking": tracking,
            "settings": FakeSettings(),
        }
        mcp_server = MagicMock()
        mcp_server.get_context.return_value = ctx
        return mcp_server

    def test_returns_full_documents(self, tmp_path):
        # Create a test file
        doc = tmp_path / "guide.md"
        doc.write_text("# Full Guide\n\nThis is the full content.")

        retriever = MagicMock()
        retriever.search.return_value = [
            FakeResult(
                document="chunk of guide",
                metadata={"source_path": str(doc)},
                score=0.95,
            ),
        ]

        tracking = MagicMock()
        tracking.get_file.return_value = {
            "path": str(doc),
            "status": "complete",
            "chunk_count": 2,
        }

        import app.mcp.tools.search_documents as mod

        mod._mcp = self._make_context(retriever, tracking)

        result = mod.handler("guide", top_k=3, max_chars=15000)

        assert len(result["documents"]) == 1
        assert result["documents"][0]["content"] == "# Full Guide\n\nThis is the full content."
        assert result["documents"][0]["score"] == 0.95
        assert result["total_chars"] > 0

    def test_deduplicates_by_source(self, tmp_path):
        doc = tmp_path / "guide.md"
        doc.write_text("content")

        retriever = MagicMock()
        # Two chunks from the same file
        retriever.search.return_value = [
            FakeResult(document="chunk1", metadata={"source_path": str(doc)}, score=0.9),
            FakeResult(document="chunk2", metadata={"source_path": str(doc)}, score=0.8),
        ]

        tracking = MagicMock()
        tracking.get_file.return_value = {"path": str(doc), "status": "complete", "chunk_count": 2}

        import app.mcp.tools.search_documents as mod

        mod._mcp = self._make_context(retriever, tracking)

        result = mod.handler("guide")
        assert len(result["documents"]) == 1
        # Should use the higher score
        assert result["documents"][0]["score"] == 0.9

    def test_respects_max_chars(self, tmp_path):
        doc1 = tmp_path / "big.md"
        doc1.write_text("A" * 10000)
        doc2 = tmp_path / "small.md"
        doc2.write_text("B" * 100)

        retriever = MagicMock()
        retriever.search.return_value = [
            FakeResult(document="chunk", metadata={"source_path": str(doc1)}, score=0.95),
            FakeResult(document="chunk", metadata={"source_path": str(doc2)}, score=0.85),
        ]

        tracking = MagicMock()
        tracking.get_file.side_effect = lambda p: {"path": p, "status": "complete", "chunk_count": 1}

        import app.mcp.tools.search_documents as mod

        mod._mcp = self._make_context(retriever, tracking)

        # Budget of 5000 chars — first doc (10000 chars) gets truncated
        result = mod.handler("test", top_k=5, max_chars=5000)
        assert result["total_chars"] <= 5100  # small overshoot from truncation marker
        assert "[... truncated ...]" in result["documents"][0]["content"]

    def test_skips_untracked_files(self, tmp_path):
        doc = tmp_path / "untracked.md"
        doc.write_text("content")

        retriever = MagicMock()
        retriever.search.return_value = [
            FakeResult(document="chunk", metadata={"source_path": str(doc)}, score=0.9),
        ]

        tracking = MagicMock()
        tracking.get_file.return_value = None  # Not tracked

        import app.mcp.tools.search_documents as mod

        mod._mcp = self._make_context(retriever, tracking)

        result = mod.handler("test")
        assert len(result["documents"]) == 0

    def test_empty_results(self):
        retriever = MagicMock()
        retriever.search.return_value = []

        tracking = MagicMock()

        import app.mcp.tools.search_documents as mod

        mod._mcp = self._make_context(retriever, tracking)

        result = mod.handler("nonexistent query")
        assert result["documents"] == []
        assert result["total_chars"] == 0
