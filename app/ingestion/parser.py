"""Parse markdown files and split into chunks by headers."""

import os
import re
from dataclasses import dataclass, field

import logging

import frontmatter
import yaml

logger = logging.getLogger(__name__)


def _doc_breadcrumb(filepath: str, source_root: str,
                    heading: str) -> str:
    """Build a short breadcrumb like 'From: project/filename > Section'."""
    if source_root:
        rel = os.path.relpath(filepath, source_root)
    else:
        rel = os.path.basename(filepath)
    # Strip .md extension for readability
    name = re.sub(r"\.md$", "", rel, flags=re.IGNORECASE)
    parts = ["From:", name]
    if heading:
        parts.append(">")
        parts.append(heading)
    return " ".join(parts)


@dataclass
class Chunk:
    """A chunk of parsed markdown content with associated metadata."""

    content: str
    metadata: dict = field(default_factory=dict)

    @property
    def chunk_id(self) -> str:
        """Generate a unique identifier for this chunk."""
        path = self.metadata.get("source_path", "")
        heading = self.metadata.get("heading", "")
        idx = self.metadata.get("chunk_index", 0)
        return f"{path}::{heading}::{idx}"


def parse_markdown(filepath: str,
                   source_root: str = "") -> list[Chunk]:
    """Parse a markdown file into header-based chunks."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()

    try:
        post = frontmatter.loads(raw)
        front = dict(post.metadata) if post.metadata else {}
        content = post.content
    except yaml.YAMLError as e:
        logger.warning(
            "Bad YAML frontmatter in %s — all metadata (title, tags) will be lost for this file: %s",
            filepath, e,
        )
        front = {}
        content = raw

    chunks = _split_by_headers(content)

    result: list[Chunk] = []
    for i, (heading, body) in enumerate(chunks):
        text = body.strip()
        if not text:
            continue

        # Contextual retrieval: prepend breadcrumb so the embedding
        # captures which document and section this chunk belongs to.
        breadcrumb = _doc_breadcrumb(filepath, source_root, heading)
        if heading:
            text = f"{breadcrumb}\n\n# {heading}\n\n{text}"
        else:
            text = f"{breadcrumb}\n\n{text}"

        metadata = {
            "source_path": filepath,
            "source_root": source_root,
            "heading": heading or f"section_{i}",
            "chunk_index": i,
            "frontmatter": front,
        }

        if front.get("title"):
            metadata["title"] = front["title"]
        if front.get("tags"):
            metadata["tags"] = front["tags"]

        result.append(Chunk(content=text, metadata=metadata))

    return result


def parse_markdown_content(
    raw: str, virtual_path: str, source_root: str = "",
) -> list[Chunk]:
    """Parse raw markdown text into header-based chunks.

    Like parse_markdown but takes content directly instead of reading
    from disk.  Used for bucket inline document uploads where the file
    doesn't exist on the server's filesystem.
    """
    try:
        post = frontmatter.loads(raw)
        front = dict(post.metadata) if post.metadata else {}
        content = post.content
    except yaml.YAMLError:
        front = {}
        content = raw

    chunks = _split_by_headers(content)

    result: list[Chunk] = []
    for i, (heading, body) in enumerate(chunks):
        text = body.strip()
        if not text:
            continue

        breadcrumb = _doc_breadcrumb(virtual_path, source_root, heading)
        if heading:
            text = f"{breadcrumb}\n\n# {heading}\n\n{text}"
        else:
            text = f"{breadcrumb}\n\n{text}"

        metadata = {
            "source_path": virtual_path,
            "source_root": source_root,
            "heading": heading or f"section_{i}",
            "chunk_index": i,
            "frontmatter": front,
        }

        if front.get("title"):
            metadata["title"] = front["title"]
        if front.get("tags"):
            metadata["tags"] = front["tags"]

        result.append(Chunk(content=text, metadata=metadata))

    return result


def _split_by_headers(
    content: str,
) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) tuples by headers."""
    header_pattern = re.compile(
        r"^(#{1,6})\s+(.+)$", re.MULTILINE
    )

    matches = list(header_pattern.finditer(content))

    if not matches:
        return [("", content)]

    sections: list[tuple[str, str]] = []

    # Content before first header
    pre_header = content[: matches[0].start()].strip()
    if pre_header:
        sections.append(("", pre_header))

    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = (
            matches[i + 1].start()
            if i + 1 < len(matches)
            else len(content)
        )
        body = content[start:end].strip()
        sections.append((heading, body))

    return sections


def _split_long_paragraph(para: str, max_size: int) -> list[str]:
    """Split a long paragraph by sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", para)
    chunks: list[str] = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 <= max_size:
            current = f"{current} {sent}" if current else sent
        else:
            if current:
                chunks.append(current.strip())
            current = sent
    if current:
        chunks.append(current.strip())
    return chunks


def chunk_text(text: str, max_size: int = 512,
               overlap: int = 50,
               min_chunk_size: int = 200) -> list[str]:
    """Split text into chunks respecting paragraph boundaries.

    Chunks shorter than *min_chunk_size* (e.g. a bare heading) are kept
    as a prefix for the next chunk rather than emitted on their own.
    """
    if len(text) <= max_size:
        return [text]

    chunks: list[str] = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current and len(current.strip()) >= min_chunk_size:
                chunks.append(current.strip())
                current = ""
            # If current is too short (heading stub), keep it as prefix
            if len(para) > max_size:
                prefix = f"{current}\n\n" if current else ""
                sub_chunks = _split_long_paragraph(para, max_size)
                if sub_chunks:
                    sub_chunks[0] = (prefix + sub_chunks[0]).strip()
                chunks.extend(sub_chunks)
                current = ""
            else:
                current = f"{current}\n\n{para}" if current else para

    if current.strip():
        chunks.append(current.strip())

    # Apply overlap
    if overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-overlap:]
            overlapped.append(prev_tail + " " + chunks[i])
        chunks = overlapped

    return chunks


def parse_and_chunk(
    filepath: str, source_root: str = "",
    max_chunk_size: int = 512, overlap: int = 50,
) -> list[Chunk]:
    """Parse a markdown file and split into size-limited chunks."""
    raw_chunks = parse_markdown(filepath, source_root)
    result: list[Chunk] = []
    global_idx = 0

    for chunk in raw_chunks:
        sub_texts = chunk_text(
            chunk.content, max_chunk_size, overlap
        )
        for sub in sub_texts:
            meta = dict(chunk.metadata)
            meta["chunk_index"] = global_idx
            result.append(Chunk(content=sub, metadata=meta))
            global_idx += 1

    return result
