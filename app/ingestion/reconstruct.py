"""Rebuild document content from stored chunks.

Inverse of :func:`app.ingestion.parser.parse_and_chunk`. The chunker
prepends two things to chunks that must be undone when reconstructing a
document for display or export:

- a ``From: path > Section`` breadcrumb (contextual retrieval), on the
  first chunk of each section
- the tail of the previous chunk (``embeddings.chunk_overlap``), on every
  subsequent chunk within a section

Joining stored chunks without removing the overlap repeats the seam text
at every chunk boundary — usually starting mid-word, since the overlap is
character-based.
"""

# Upper bound from config validation (embeddings.chunk_overlap <= 4096).
# The index may have been written under a different overlap setting than
# the current one, so the actual overlap is detected per seam rather than
# read from config.
_MAX_OVERLAP = 4096
# Below this length a prefix/suffix match is plausibly coincidence rather
# than chunker overlap, so it is left untouched.
_MIN_OVERLAP = 10


def _strip_breadcrumb(doc: str) -> str:
    """Remove the ``From: ...`` wrapper header added by the chunker."""
    lines = doc.split("\n", 2)
    if lines[0].startswith("From:") and len(lines) > 2:
        return lines[2]
    return doc


def _strip_overlap(prev: str, cur: str) -> str:
    """Remove cur's leading copy of prev's tail (the chunker's overlap).

    The chunker builds overlapped chunks as ``prev[-overlap:] + " " + cur``,
    so the longest suffix of *prev* that prefixes *cur* (followed by a
    space) is the overlap. Section-first chunks carry no overlap and pass
    through unchanged.
    """
    limit = min(len(prev), len(cur) - 1, _MAX_OVERLAP)
    for k in range(limit, _MIN_OVERLAP - 1, -1):
        if cur.startswith(prev[-k:] + " "):
            return cur[k + 1:]
    return cur


def reconstruct_chunks(docs: list[str]) -> str:
    """Join chunk documents (ordered by chunk_index) into clean content.

    Strips breadcrumbs, removes inter-chunk overlap, and joins with blank
    lines. Callers are responsible for ordering ``docs`` by chunk_index.
    """
    parts = [_strip_breadcrumb(doc) for doc in docs]
    for i in range(1, len(parts)):
        # parts[i-1] is already de-overlapped at its front; its tail — which
        # is what the chunker copied forward — is unaffected by that.
        parts[i] = _strip_overlap(parts[i - 1], parts[i])
    return "\n\n".join(parts)
