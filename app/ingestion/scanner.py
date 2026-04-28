"""Discover and scan markdown files from configured source directories."""

import fnmatch
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Metadata about a discovered markdown file."""

    path: str
    relative_path: str
    size: int
    modified: float
    content_hash: str
    source_root: str


def _matches_ignore(path: str, patterns: list[str]) -> bool:
    """Check whether a path matches any of the ignore patterns."""
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def _glob_to_regex(pattern: str) -> re.Pattern:
    """Convert a glob pattern to a regex where * does not cross / boundaries."""
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern[i:i+3] == "**/":
            parts.append("(?:[^/]+/)*")
            i += 3
        elif pattern[i:i+2] == "**":
            parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(parts) + "$")


def matches_source_include(rel_path: str, include: list[str], exclude: list[str]) -> bool:
    """Return True if rel_path is permitted by the source's include/exclude filters.

    *  does not cross directory boundaries (unlike fnmatch).
    ** matches any number of path components.
    An empty include list means all files are permitted.
    """
    if not include:
        return True
    if not any(_glob_to_regex(p).match(rel_path) for p in include):
        return False
    if exclude and any(_glob_to_regex(p).match(rel_path) for p in exclude):
        return False
    return True


def compute_file_hash(filepath: str) -> str:
    """Compute the SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def discover_sources(
    sources: list[str],
    ignore_patterns: list[str],
    source_filters: dict[str, dict] | None = None,
) -> list[dict]:
    """Walk all source directories and return lightweight file info (no hash).

    Returns a list of dicts with keys: path, source_root, file_size, mtime.
    This is fast enough for the Browse UI since it skips content hashing.

    source_filters maps source path → {include: [...], exclude: [...]} for
    project-root-derived sources. Files not matching their source's include
    patterns are excluded.
    """
    files: list[dict] = []
    seen: set[str] = set()
    _filters = source_filters or {}

    for source in sources:
        source_path = Path(source).resolve()
        if not source_path.exists():
            logger.warning("Configured source does not exist, skipping: %s", source_path)
            continue

        src_key = str(source_path)
        filt = _filters.get(src_key, {})
        include = filt.get("include", [])
        exclude = filt.get("exclude", [])

        if source_path.is_file() and source_path.suffix == ".md":
            abs_path = str(source_path)
            if abs_path not in seen and not _matches_ignore(abs_path, ignore_patterns):
                seen.add(abs_path)
                stat = source_path.stat()
                files.append({
                    "path": abs_path,
                    "source_root": str(source_path.parent),
                    "file_size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
            continue

        for root, dirs, filenames in os.walk(source_path):
            dirs[:] = [
                d for d in dirs
                if not _matches_ignore(os.path.join(root, d, ""), ignore_patterns)
            ]
            for fname in filenames:
                if not fname.endswith(".md"):
                    continue
                full_path = os.path.join(root, fname)
                abs_path = str(Path(full_path).resolve())
                if abs_path in seen or _matches_ignore(abs_path, ignore_patterns):
                    continue
                rel_path = os.path.relpath(full_path, source_path)
                if not matches_source_include(rel_path, include, exclude):
                    continue
                seen.add(abs_path)
                stat = os.stat(full_path)
                files.append({
                    "path": abs_path,
                    "source_root": str(source_path),
                    "file_size": stat.st_size,
                    "mtime": stat.st_mtime,
                })

    return files


def scan_sources(
    sources: list[str],
    ignore_patterns: list[str],
    source_filters: dict[str, dict] | None = None,
) -> list[FileInfo]:
    """Walk all source directories and return FileInfo for each markdown file.

    source_filters maps source path → {include: [...], exclude: [...]} for
    project-root-derived sources. Files not matching their source's include
    patterns are excluded.
    """
    files: list[FileInfo] = []
    seen: set[str] = set()
    _filters = source_filters or {}

    for source in sources:
        source_path = Path(source).resolve()
        if not source_path.exists():
            logger.warning("Configured source does not exist, skipping: %s", source_path)
            continue

        src_key = str(source_path)
        filt = _filters.get(src_key, {})
        include = filt.get("include", [])
        exclude = filt.get("exclude", [])

        if source_path.is_file() and source_path.suffix == ".md":
            abs_path = str(source_path)
            if abs_path not in seen and not _matches_ignore(abs_path, ignore_patterns):
                seen.add(abs_path)
                stat = source_path.stat()
                files.append(FileInfo(
                    path=abs_path,
                    relative_path=source_path.name,
                    size=stat.st_size,
                    modified=stat.st_mtime,
                    content_hash=compute_file_hash(abs_path),
                    source_root=str(source_path.parent),
                ))
            continue

        for root, dirs, filenames in os.walk(source_path):
            dirs[:] = [
                d for d in dirs
                if not _matches_ignore(os.path.join(root, d, ""), ignore_patterns)
            ]

            for fname in filenames:
                if not fname.endswith(".md"):
                    continue

                full_path = os.path.join(root, fname)
                abs_path = str(Path(full_path).resolve())

                if abs_path in seen:
                    continue

                if _matches_ignore(abs_path, ignore_patterns):
                    continue

                rel_path = os.path.relpath(full_path, source_path)
                if not matches_source_include(rel_path, include, exclude):
                    continue

                seen.add(abs_path)
                stat = os.stat(full_path)

                files.append(FileInfo(
                    path=abs_path,
                    relative_path=rel_path,
                    size=stat.st_size,
                    modified=stat.st_mtime,
                    content_hash=compute_file_hash(abs_path),
                    source_root=str(source_path),
                ))

    return files
