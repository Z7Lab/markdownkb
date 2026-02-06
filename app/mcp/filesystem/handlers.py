"""Filesystem exploration tools for browsing directories and reading files."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FileEntry:
    """Represents a single file or directory entry."""

    name: str
    path: str
    is_dir: bool
    size: int = 0


def list_directory(path: str, max_depth: int = 1) -> list[FileEntry]:
    """List the contents of a directory up to a maximum depth."""
    target = Path(path).resolve()
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    if not target.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    entries: list[FileEntry] = []
    _walk(target, entries, current_depth=0, max_depth=max_depth)
    return entries


def _walk(directory: Path, entries: list[FileEntry],
          current_depth: int, max_depth: int):
    """Recursively walk a directory tree collecting FileEntry objects."""
    try:
        for item in sorted(directory.iterdir()):
            if item.name.startswith("."):
                continue

            entry = FileEntry(
                name=item.name,
                path=str(item),
                is_dir=item.is_dir(),
                size=item.stat().st_size if item.is_file() else 0,
            )
            entries.append(entry)

            if item.is_dir() and current_depth < max_depth:
                _walk(item, entries, current_depth + 1, max_depth)
    except PermissionError:
        logger.warning("Permission denied: %s", directory)


def read_file(path: str, max_size: int = 1_000_000) -> str:
    """Read a file's contents, raising errors for missing, directory, or oversized files."""
    target = Path(path).resolve()
    if not target.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not target.is_file():
        raise IsADirectoryError(f"Not a file: {path}")

    size = target.stat().st_size
    if size > max_size:
        raise ValueError(f"File too large ({size} bytes, max {max_size})")

    return target.read_text(encoding="utf-8", errors="replace")


def get_file_info(path: str) -> dict:
    """Return a dictionary of metadata about a file or directory."""
    target = Path(path).resolve()
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    stat = target.stat()
    return {
        "path": str(target),
        "name": target.name,
        "is_dir": target.is_dir(),
        "is_file": target.is_file(),
        "size": stat.st_size,
        "modified": stat.st_mtime,
        "extension": target.suffix,
    }


def find_files(directory: str, pattern: str = "*.md",
               max_results: int = 100) -> list[str]:
    """Find files matching a glob pattern within a directory."""
    target = Path(directory).resolve()
    if not target.exists():
        return []

    results: list[str] = []
    for match in target.rglob(pattern):
        if match.is_file():
            results.append(str(match))
            if len(results) >= max_results:
                break

    return results


def format_tree(path: str, max_depth: int = 2) -> str:
    """Format a directory listing as an ASCII tree string."""
    entries = list_directory(path, max_depth=max_depth)
    if not entries:
        return f"{path}/ (empty)"

    root = Path(path).resolve()
    lines = [f"{root.name}/"]

    for entry in entries:
        rel = os.path.relpath(entry.path, root)
        depth = rel.count(os.sep)
        indent = "    " * depth

        if entry.is_dir:
            lines.append(f"{indent}├── {entry.name}/")
        else:
            size_str = _format_size(entry.size)
            lines.append(f"{indent}├── {entry.name} ({size_str})")

    return "\n".join(lines)


def _format_size(size: int) -> str:
    """Format a byte count into a human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
