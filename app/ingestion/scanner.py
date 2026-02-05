"""Discover and scan markdown files from configured source directories."""

import fnmatch
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path


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


def compute_file_hash(filepath: str) -> str:
    """Compute the SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_sources(sources: list[str], ignore_patterns: list[str]) -> list[FileInfo]:
    """Walk all source directories and return FileInfo for each markdown file."""
    files: list[FileInfo] = []
    seen: set[str] = set()

    for source in sources:
        source_path = Path(source).resolve()
        if not source_path.exists():
            continue

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
            # Filter out ignored directories in-place for efficiency
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

                seen.add(abs_path)
                stat = os.stat(full_path)
                rel_path = os.path.relpath(full_path, source_path)

                files.append(FileInfo(
                    path=abs_path,
                    relative_path=rel_path,
                    size=stat.st_size,
                    modified=stat.st_mtime,
                    content_hash=compute_file_hash(abs_path),
                    source_root=str(source_path),
                ))

    return files
