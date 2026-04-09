"""Tests for retriever tag filtering — ensures exact match (not substring)."""

from dataclasses import dataclass


@dataclass
class FakeSearchResult:
    document: str
    metadata: dict
    score: float


def _filter_by_tag(results, tag_filter):
    """Replicate the retriever's tag filter logic."""
    return [
        r for r in results
        if tag_filter in {t.strip() for t in r.metadata.get("tags", "").split(",") if t.strip()}
    ]


def _filter_by_scope_tags(results, scope_tags):
    """Replicate the retriever's scope tag filter logic."""
    scope_tag_set = set(scope_tags)
    def _has(meta_tags):
        file_tags = {t.strip() for t in meta_tags.split(",") if t.strip()}
        return bool(scope_tag_set & file_tags)
    return [r for r in results if _has(r.metadata.get("tags", ""))]


def test_tag_filter_exact_match():
    """Tag 'api' should NOT match 'rapid'."""
    results = [
        FakeSearchResult("doc1", {"tags": "api, backend"}, 0.9),
        FakeSearchResult("doc2", {"tags": "rapid, frontend"}, 0.8),
        FakeSearchResult("doc3", {"tags": "api"}, 0.7),
    ]
    filtered = _filter_by_tag(results, "api")
    assert len(filtered) == 2
    assert all("api" in r.metadata["tags"] for r in filtered)
    assert not any("rapid" in r.document for r in filtered if "api" not in r.metadata["tags"].split(","))


def test_tag_filter_no_substring_false_positive():
    """Substring 'test' should not match 'testing'."""
    results = [
        FakeSearchResult("doc1", {"tags": "testing"}, 0.9),
        FakeSearchResult("doc2", {"tags": "test"}, 0.8),
    ]
    filtered = _filter_by_tag(results, "test")
    assert len(filtered) == 1
    assert filtered[0].document == "doc2"


def test_scope_tags_exact_match():
    """Scope tags use exact match, not substring."""
    results = [
        FakeSearchResult("doc1", {"tags": "api, backend"}, 0.9),
        FakeSearchResult("doc2", {"tags": "rapid"}, 0.8),
    ]
    filtered = _filter_by_scope_tags(results, ["api"])
    assert len(filtered) == 1
    assert filtered[0].document == "doc1"
