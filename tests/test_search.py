"""Tests for search endpoints."""

import pytest


@pytest.mark.asyncio
async def test_search_returns_results(client):
    resp = await client.post("/api/search", json={"query": "test query"})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "search_id" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["document"] == "Test document content"
    assert data["results"][0]["score"] == 0.9


@pytest.mark.asyncio
async def test_search_empty_query_rejected(client):
    resp = await client.post("/api/search", json={"query": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_with_top_k(client):
    resp = await client.post("/api/search", json={"query": "test", "top_k": 3})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_top_k_out_of_range(client):
    resp = await client.post("/api/search", json={"query": "test", "top_k": 100})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_folders_paginated(client):
    resp = await client.get("/api/folders")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 3
    assert data["items"] == ["folder1", "folder2", "folder3"]


@pytest.mark.asyncio
async def test_folders_with_limit(client):
    resp = await client.get("/api/folders?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3
    assert data["offset"] == 0
    assert data["limit"] == 2


@pytest.mark.asyncio
async def test_tags_paginated(client):
    resp = await client.get("/api/tags")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_list_searches(client):
    resp = await client.get("/api/searches")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 1
    assert data["items"][0]["query"] == "test query"


@pytest.mark.asyncio
async def test_delete_search(client):
    resp = await client.delete("/api/searches/srch001")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_search_saves_result_metadata(client, app):
    """Test that search saves result paths, count, scores, and full result data."""
    resp = await client.post("/api/search", json={"query": "test query"})
    assert resp.status_code == 200

    # Verify save_search was called with result metadata
    searchdb = app.state.searchdb
    searchdb.save_search.assert_called_once()
    call_args = searchdb.save_search.call_args

    # Check that result_paths, result_count, result_details, and result_data were passed
    assert "result_paths" in call_args.kwargs
    assert "result_count" in call_args.kwargs
    assert "result_details" in call_args.kwargs
    assert "result_data" in call_args.kwargs
    assert call_args.kwargs["result_paths"] == ["/tmp/test-source/doc.md"]
    assert call_args.kwargs["result_count"] == 1
    assert call_args.kwargs["result_details"] == [{"path": "/tmp/test-source/doc.md", "score": 0.9}]
    # Verify result_data contains full grouped results
    assert len(call_args.kwargs["result_data"]) == 1
    assert call_args.kwargs["result_data"][0]["score"] == 0.9
    assert "snippets" in call_args.kwargs["result_data"][0]


@pytest.mark.asyncio
async def test_load_historical_search(client, app):
    """Test loading a historical search returns stored data fast (no re-search)."""
    original_result = {
        "document": "Test document content",
        "snippets": [],
        "metadata": {"source_path": "/tmp/test-source/doc.md"},
        "score": 0.9,
        "chunk_count": 1,
        "score_min": 0.9,
        "score_max": 0.9,
        "score_avg": 0.9,
    }
    app.state.searchdb.get_search.return_value = {
        "id": "srch001",
        "query": "test query",
        "folder": None,
        "tag": None,
        "summary": "Original AI summary",
        "result_paths": ["/tmp/test-source/doc.md"],
        "result_count": 1,
        "result_details": [{"path": "/tmp/test-source/doc.md", "score": 0.9}],
        "result_data": [original_result],
        "created_at": "2024-01-01 00:00:00",
    }

    resp = await client.get("/api/searches/srch001/load")
    assert resp.status_code == 200
    data = resp.json()

    # Fast load returns stored data without comparison fields
    assert data["is_historical"] is True
    assert data["summary"] == "Original AI summary"
    assert data["created_at"] == "2024-01-01 00:00:00"
    assert "version_count" in data

    # Comparison fields are NOT in the fast load response
    assert "stored_result_count" not in data
    assert "score_changes" not in data

    # Verify preserved results are returned (from result_data)
    assert len(data["results"]) == 1
    assert data["results"][0]["document"] == "Test document content"

    # Verify mark_viewed was called
    app.state.searchdb.mark_viewed.assert_called_once_with("srch001")


@pytest.mark.asyncio
async def test_compare_historical_search_detects_changes(client, app):
    """Test that compare endpoint detects KB changes."""
    app.state.searchdb.get_search.return_value = {
        "id": "srch001",
        "query": "test query",
        "folder": None,
        "tag": None,
        "summary": "Original summary",
        "result_paths": ["/tmp/old-file.md", "/tmp/removed-file.md"],
        "result_count": 2,
        "result_details": [
            {"path": "/tmp/old-file.md", "score": 0.85},
            {"path": "/tmp/removed-file.md", "score": 0.75},
        ],
        "result_data": [],
        "created_at": "2024-01-01 00:00:00",
    }

    # Current search returns different results
    # (retriever mock in conftest returns ["/tmp/test-source/doc.md"])

    resp = await client.get("/api/searches/srch001/compare")
    assert resp.status_code == 200
    data = resp.json()

    # Verify change detection
    assert data["results_changed"] is True
    assert data["stored_result_count"] == 2
    assert data["current_result_count"] == 1

    # Verify missing and new files
    assert len(data["missing_files"]) == 2
    assert "/tmp/old-file.md" in data["missing_files"]
    assert "/tmp/removed-file.md" in data["missing_files"]
    assert len(data["new_files"]) == 1
    assert "/tmp/test-source/doc.md" in data["new_files"]


@pytest.mark.asyncio
async def test_load_historical_search_not_found(client, app):
    """Test loading a non-existent search returns 404."""
    app.state.searchdb.get_search.return_value = None
    resp = await client.get("/api/searches/nonexistent/load")
    assert resp.status_code == 404
    data = resp.json()
    assert data["detail"] == "Search not found"


@pytest.mark.asyncio
async def test_search_response_is_not_historical(client):
    """Test that new search responses have is_historical=False."""
    resp = await client.post("/api/search", json={"query": "test query"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_historical"] is False


@pytest.mark.asyncio
async def test_compare_historical_search_detects_score_changes(client, app):
    """Test that compare endpoint detects relevance score changes."""
    app.state.searchdb.get_search.return_value = {
        "id": "srch001",
        "query": "test query",
        "folder": None,
        "tag": None,
        "summary": "Original summary",
        "result_paths": ["/tmp/test-source/doc.md"],
        "result_count": 1,
        "result_details": [{"path": "/tmp/test-source/doc.md", "score": 0.75}],
        "result_data": [],
        "created_at": "2024-01-01 00:00:00",
    }

    # Current search returns same file with different score (0.9)
    # (retriever mock in conftest returns score: 0.9)

    resp = await client.get("/api/searches/srch001/compare")
    assert resp.status_code == 200
    data = resp.json()

    # Verify score change detection
    assert data["results_changed"] is True
    assert len(data["score_changes"]) == 1
    assert data["score_changes"][0]["path"] == "/tmp/test-source/doc.md"
    assert data["score_changes"][0]["old_score"] == 0.75
    assert data["score_changes"][0]["new_score"] == 0.9
    assert abs(data["score_changes"][0]["change"] - 0.15) < 0.001

    # Verify no missing or new files (same file in both)
    assert len(data["missing_files"]) == 0
    assert len(data["new_files"]) == 0


@pytest.mark.asyncio
async def test_get_search_versions(client, app):
    """Test getting all versions of a search chain."""
    app.state.searchdb.get_search_versions.return_value = [
        {"id": "srch001", "query": "test query", "result_count": 3, "summary": "v1", "created_at": "2024-01-01", "parent_id": None},
        {"id": "srch002", "query": "test query", "result_count": 5, "summary": "v2", "created_at": "2024-01-02", "parent_id": "srch001"},
    ]

    resp = await client.get("/api/searches/srch001/versions")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["versions"]) == 2
    assert data["versions"][0]["id"] == "srch001"
    assert data["versions"][0]["parent_id"] is None  # Original
    assert data["versions"][1]["id"] == "srch002"
    assert data["versions"][1]["parent_id"] == "srch001"  # Re-query


@pytest.mark.asyncio
async def test_get_search_versions_not_found(client, app):
    """Test versions endpoint returns 404 for non-existent search."""
    app.state.searchdb.get_search_versions.return_value = []
    resp = await client.get("/api/searches/nonexistent/versions")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_requery_links_parent_id(client, app):
    """Test that re-query passes parent_id to link search versions."""
    # Mock get_search to return a root search (no parent_id)
    app.state.searchdb.get_search.return_value = {
        "id": "srch001",
        "query": "test query",
        "folder": None,
        "tag": None,
        "parent_id": None,
        "result_paths": [],
        "result_count": 0,
        "result_details": [],
        "result_data": [],
        "created_at": "2024-01-01 00:00:00",
    }

    resp = await client.post("/api/search", json={
        "query": "test query",
        "parent_id": "srch001",
    })
    assert resp.status_code == 200

    # Verify save_search was called with parent_id
    call_args = app.state.searchdb.save_search.call_args
    assert call_args.kwargs["parent_id"] == "srch001"


@pytest.mark.asyncio
async def test_requery_resolves_chain_root(client, app):
    """Test that re-query from a child resolves to the root parent_id."""
    # Mock get_search to return a child search (has parent_id)
    app.state.searchdb.get_search.return_value = {
        "id": "srch002",
        "query": "test query",
        "folder": None,
        "tag": None,
        "parent_id": "srch001",  # This search's parent is srch001
        "result_paths": [],
        "result_count": 0,
        "result_details": [],
        "result_data": [],
        "created_at": "2024-01-02 00:00:00",
    }

    resp = await client.post("/api/search", json={
        "query": "test query",
        "parent_id": "srch002",  # Re-query from child
    })
    assert resp.status_code == 200

    # Verify save_search was called with root parent_id (srch001), not srch002
    call_args = app.state.searchdb.save_search.call_args
    assert call_args.kwargs["parent_id"] == "srch001"
