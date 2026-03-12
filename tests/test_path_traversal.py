"""Tests for path traversal prevention in MCP server."""

from pathlib import Path


def test_path_traversal_sibling_directory():
    """Ensure /docs-private does NOT pass when /docs is a source."""
    sources = ["/data/docs"]
    resolved = "/data/docs-private/secret.md"

    in_source = any(
        resolved == str(Path(s).resolve())
        or resolved.startswith(str(Path(s).resolve()) + "/")
        for s in sources
    )
    assert in_source is False


def test_path_within_source():
    """Files within a source directory should pass."""
    sources = ["/data/docs"]
    resolved = "/data/docs/readme.md"

    in_source = any(
        resolved == str(Path(s).resolve())
        or resolved.startswith(str(Path(s).resolve()) + "/")
        for s in sources
    )
    assert in_source is True


def test_path_exact_match_source():
    """The source directory itself should match."""
    sources = ["/data/docs"]
    resolved = "/data/docs"

    in_source = any(
        resolved == str(Path(s).resolve())
        or resolved.startswith(str(Path(s).resolve()) + "/")
        for s in sources
    )
    assert in_source is True


def test_path_nested_subdirectory():
    """Nested paths within source should pass."""
    sources = ["/data/docs"]
    resolved = "/data/docs/sub/deep/file.md"

    in_source = any(
        resolved == str(Path(s).resolve())
        or resolved.startswith(str(Path(s).resolve()) + "/")
        for s in sources
    )
    assert in_source is True
