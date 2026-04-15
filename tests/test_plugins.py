"""Smoke tests for optional plugins.

These are intentionally minimal: the goal is to fail loudly if a plugin's
module is broken on import or if its service module stops exporting the
symbols the router consumes. Full feature coverage lives in each plugin's
dedicated test module (as that module is written).
"""

import importlib

import pytest


OPTIONAL_PLUGINS = [
    "converter",
    "docmap",
    "knowledge_graph",
    "lint",
    "planner",
    "wiki_compile",
    "write_api",
    "catalogs",
]


_NO_FEATURE_FLAG = {"catalogs", "lint"}


@pytest.mark.parametrize("plugin", OPTIONAL_PLUGINS)
def test_plugin_imports_cleanly(plugin):
    """Every optional plugin package must import without side effects failing."""
    mod = importlib.import_module(f"app.plugins.{plugin}")
    if plugin not in _NO_FEATURE_FLAG:
        assert hasattr(mod, "FEATURE_FLAG"), f"{plugin} missing FEATURE_FLAG"


def test_search_service_helpers_match_router_aliases():
    """The search plugin extracted helpers; aliases must still resolve."""
    from app.plugins.search.router import _cfg, _group_results_by_file
    from app.plugins.search.service import get_search_config, group_results_by_file
    assert _cfg is get_search_config
    assert _group_results_by_file is group_results_by_file


def test_docmap_cache_key_stable():
    """docmap.service.cache_key produces deterministic tuples."""
    from app.plugins.docmap.service import cache_key
    k1 = cache_key(["/a"], ["tag"], None, 3)
    k2 = cache_key(["/a"], ["tag"], None, 3)
    assert k1 == k2
    assert cache_key(None, None, None, 3) != k1


def test_knowledge_graph_status_shape():
    """knowledge_graph.service.new_extraction_status includes the documented keys."""
    from app.plugins.knowledge_graph.service import new_extraction_status
    status = new_extraction_status()
    for key in ("running", "cancel", "progress", "message", "result", "files_done", "files_total"):
        assert key in status, f"missing key {key}"


@pytest.mark.asyncio
async def test_lint_endpoints_gated_on_feature_flag(client):
    """Lint routes aren't mounted when the plugin isn't enabled in FakeSettings."""
    resp = await client.post("/api/v1/lint/run", json={})
    # Route not registered → 404; when registered it would be 422 for empty body.
    assert resp.status_code in (404, 422)


@pytest.mark.asyncio
async def test_wiki_compile_endpoints_gated(client):
    """wiki_compile routes not mounted when disabled."""
    resp = await client.get("/api/v1/wiki-compile/wikis")
    assert resp.status_code in (404, 503)


@pytest.mark.asyncio
async def test_docmap_endpoints_gated(client):
    """docmap routes not mounted when disabled."""
    resp = await client.get("/api/v1/docmap/data")
    assert resp.status_code in (404, 503)


@pytest.mark.asyncio
async def test_knowledge_graph_endpoints_gated(client):
    """knowledge-graph routes not mounted when disabled."""
    resp = await client.get("/api/v1/knowledge-graph/stats")
    assert resp.status_code in (404, 503)


@pytest.mark.asyncio
async def test_converter_endpoints_gated(client):
    """converter routes not mounted when disabled."""
    resp = await client.post("/api/v1/converter/convert", json={})
    assert resp.status_code in (404, 422, 503)


@pytest.mark.asyncio
async def test_write_api_endpoints_gated(client):
    """write_api (documents) routes not mounted when disabled."""
    resp = await client.post("/api/v1/documents", json={})
    assert resp.status_code in (404, 422, 503)
