"""Tests for the consolidated scope + bucket resolution service.

This is the unit-level verification that Phase 1's ``resolve_request_scope``
behaves the same way across every caller (chat, planner, search, docmap).
Before the consolidation, planner silently dropped missing buckets while
search raised 404; these tests lock the policy down to 404.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.scope_service import (
    parse_scope_id_fallback,
    resolve_bucket_retrievers,
    resolve_request_scope,
)


class _FakeScopeDB:
    def __init__(self, scopes=None):
        self._scopes = scopes or {}

    def get(self, sid):
        return self._scopes.get(sid)


class _FakeBucketDB:
    def __init__(self, records=None):
        self._records = records or {}

    def resolve(self, bid):
        return self._records.get(bid)


class _FakeBucketService:
    def __init__(self, records=None):
        self.db = _FakeBucketDB(records)

    def get_retriever(self, bucket_id, settings):
        return f"retriever-for-{bucket_id}"


# -- parse_scope_id_fallback -------------------------------------------------


def test_parse_scope_id_fallback_prefers_list():
    assert parse_scope_id_fallback(["a", "b"], "c") == ["a", "b"]


def test_parse_scope_id_fallback_uses_legacy_when_list_empty():
    assert parse_scope_id_fallback(None, "legacy") == ["legacy"]
    assert parse_scope_id_fallback([], "legacy") == ["legacy"]


def test_parse_scope_id_fallback_none_when_both_empty():
    assert parse_scope_id_fallback(None, None) is None
    assert parse_scope_id_fallback([], None) is None


# -- resolve_bucket_retrievers ------------------------------------------------


def test_resolve_bucket_retrievers_empty_when_no_ids():
    result = resolve_bucket_retrievers(None, None, MagicMock())
    assert result == []


def test_resolve_bucket_retrievers_503_when_service_missing():
    with pytest.raises(HTTPException) as exc:
        resolve_bucket_retrievers(None, ["b1"], MagicMock())
    assert exc.value.status_code == 503


def test_resolve_bucket_retrievers_404_on_missing_bucket():
    svc = _FakeBucketService(records={"known": {"id": "known"}})
    with pytest.raises(HTTPException) as exc:
        resolve_bucket_retrievers(svc, ["missing"], MagicMock())
    assert exc.value.status_code == 404
    assert "missing" in exc.value.detail


def test_resolve_bucket_retrievers_ok():
    svc = _FakeBucketService(records={
        "b1": {"id": "b1"},
        "b2": {"id": "b2"},
    })
    result = resolve_bucket_retrievers(svc, ["b1", "b2"], MagicMock())
    assert result == ["retriever-for-b1", "retriever-for-b2"]


# -- resolve_request_scope ---------------------------------------------------


def _call_resolve(**overrides):
    base = dict(
        bucket_service=None,
        scope_ids=None,
        scope_id=None,
        bucket_ids=None,
        ad_hoc_tags=None,
        settings=MagicMock(),
        scopedb=_FakeScopeDB(),
    )
    base.update(overrides)
    return resolve_request_scope(**base)


def test_resolve_request_scope_empty_bundle_is_neutral():
    bundle = _call_resolve()
    assert bundle.scope_folders is None
    assert bundle.allowed_paths is None
    assert bundle.exclude_patterns == []
    assert bundle.bucket_retrievers == []
    assert bundle.bucket_only is False
    assert bundle.has_scope is False


def test_resolve_request_scope_with_scope_ids():
    scopes = {"s1": {"folders": ["docs"], "tags": [], "exclude_patterns": []}}
    bundle = _call_resolve(
        scope_ids=["s1"],
        scopedb=_FakeScopeDB(scopes),
    )
    assert bundle.scope_folders == ["docs"]
    assert bundle.has_scope is True


def test_resolve_request_scope_uses_legacy_scope_id():
    scopes = {"legacy": {"folders": ["archive"], "tags": [], "exclude_patterns": []}}
    bundle = _call_resolve(
        scope_id="legacy",
        scopedb=_FakeScopeDB(scopes),
    )
    assert bundle.scope_folders == ["archive"]


def test_resolve_request_scope_bucket_only_when_no_scope():
    svc = _FakeBucketService(records={"b1": {"id": "b1"}})
    bundle = _call_resolve(
        bucket_service=svc,
        bucket_ids=["b1"],
    )
    assert bundle.bucket_only is True
    assert bundle.bucket_retrievers == ["retriever-for-b1"]


def test_resolve_request_scope_not_bucket_only_with_scope():
    scopes = {"s1": {"folders": ["docs"], "tags": [], "exclude_patterns": []}}
    svc = _FakeBucketService(records={"b1": {"id": "b1"}})
    bundle = _call_resolve(
        bucket_service=svc,
        bucket_ids=["b1"],
        scope_ids=["s1"],
        scopedb=_FakeScopeDB(scopes),
    )
    assert bundle.bucket_only is False
    assert bundle.bucket_retrievers == ["retriever-for-b1"]


def test_resolve_request_scope_404_on_unknown_bucket():
    svc = _FakeBucketService(records={"known": {"id": "known"}})
    with pytest.raises(HTTPException) as exc:
        _call_resolve(bucket_service=svc, bucket_ids=["missing"])
    assert exc.value.status_code == 404


def test_resolve_request_scope_503_when_plugin_off():
    """Previously planner silently skipped — now uniform 503 everywhere."""
    with pytest.raises(HTTPException) as exc:
        _call_resolve(bucket_service=None, bucket_ids=["b1"])
    assert exc.value.status_code == 503


def test_resolve_request_scope_404_on_unknown_scope():
    with pytest.raises(HTTPException) as exc:
        _call_resolve(scope_ids=["does-not-exist"])
    assert exc.value.status_code == 404
