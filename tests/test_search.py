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
    """Test that search saves result paths, count, and scores."""
    resp = await client.post("/api/search", json={"query": "test query"})
    assert resp.status_code == 200

    # Verify save_search was called with result metadata
    searchdb = app.state.searchdb
    searchdb.save_search.assert_called_once()
    call_args = searchdb.save_search.call_args

    # Check that result_paths, result_count, and result_details were passed
    assert "result_paths" in call_args.kwargs
    assert "result_count" in call_args.kwargs
    assert "result_details" in call_args.kwargs
    assert call_args.kwargs["result_paths"] == ["/tmp/test-source/doc.md"]
    assert call_args.kwargs["result_count"] == 1
    assert call_args.kwargs["result_details"] == [{"path": "/tmp/test-source/doc.md", "score": 0.9}]


@pytest.mark.asyncio
async def test_load_historical_search(client, app):
    """Test loading a historical search with metadata."""
    # Setup mock searchdb to return a search with metadata
    app.state.searchdb.get_search.return_value = {
        "id": "srch001",
        "query": "test query",
        "folder": None,
        "tag": None,
        "summary": "Original AI summary",
        "result_paths": ["/tmp/test-source/doc.md"],
        "result_count": 1,
        "result_details": [{"path": "/tmp/test-source/doc.md", "score": 0.9}],
        "created_at": "2024-01-01 00:00:00",
    }

    resp = await client.get("/api/searches/srch001/load")
    assert resp.status_code == 200
    data = resp.json()

    # Verify historical metadata
    assert data["is_historical"] is True
    assert data["summary"] == "Original AI summary"
    assert data["created_at"] == "2024-01-01 00:00:00"
    assert data["stored_result_count"] == 1
    assert data["current_result_count"] == 1
    assert "score_changes" in data

    # Verify mark_viewed was called
    app.state.searchdb.mark_viewed.assert_called_once_with("srch001")


@pytest.mark.asyncio
async def test_load_historical_search_detects_changes(client, app):
    """Test that historical search detects KB changes."""
    # Setup mock searchdb with old result paths
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
        "created_at": "2024-01-01 00:00:00",
    }

    # Current search returns different results
    # (retriever mock in conftest returns ["/tmp/test-source/doc.md"])

    resp = await client.get("/api/searches/srch001/load")
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
async def test_load_historical_search_detects_score_changes(client, app):
    """Test that historical search detects relevance score changes."""
    # Setup mock searchdb with same file but different score
    app.state.searchdb.get_search.return_value = {
        "id": "srch001",
        "query": "test query",
        "folder": None,
        "tag": None,
        "summary": "Original summary",
        "result_paths": ["/tmp/test-source/doc.md"],
        "result_count": 1,
        "result_details": [{"path": "/tmp/test-source/doc.md", "score": 0.75}],
        "created_at": "2024-01-01 00:00:00",
    }

    # Current search returns same file with different score (0.9)
    # (retriever mock in conftest returns score: 0.9)

    resp = await client.get("/api/searches/srch001/load")
    assert resp.status_code == 200
    data = resp.json()

    # Verify score change detection
    assert data["results_changed"] is True  # Score changed
    assert len(data["score_changes"]) == 1
    assert data["score_changes"][0]["path"] == "/tmp/test-source/doc.md"
    assert data["score_changes"][0]["old_score"] == 0.75
    assert data["score_changes"][0]["new_score"] == 0.9
    assert abs(data["score_changes"][0]["change"] - 0.15) < 0.001  # 0.9 - 0.75 (allow for float precision)

    # Verify no missing or new files (same file in both)
    assert len(data["missing_files"]) == 0
    assert len(data["new_files"]) == 0
